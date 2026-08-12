#!/usr/bin/env python3
"""
Diagnostic script — verifies GeminiProvider._classify_rate_limit() against a
REAL 429 from the Gemini API, not a mocked one.

Loads the active 'gemini' row from llm_providers (model, rpm) and the real
GEMINI_API_KEY from the environment, then deliberately hammers the model past
its configured RPM with no delay — bypassing SlidingWindowStrategy (see
ProviderHandler in resilient_llm_service.py, which normally throttles calls
before they ever reach the API) so we can observe a genuine 429 instead of a
mocked one. Checks two things:

  1. What GeminiProvider._classify_rate_limit() returns for the raw exception
     (should be RateLimitKind.RPM, not RPD/None).
  2. Whether the full BaseProvider.generate() retry path backs off and
     recovers within the RPM window, instead of raising RateLimitExhausted.

Deliberately does NOT attempt to exhaust the daily (RPD) quota — that would
burn a real chunk of the account's daily budget for no need; an RPM
misclassification would already show up well before an RPD test could.

Usage:
    python scripts/verify_gemini_rate_limit_classification.py

DATABASE_URL and GEMINI_API_KEY must be set in the environment (loaded from
.env via docker-compose's env_file: for job_service).
"""
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.persistence.database import get_session, init_db
from src.infrastructure.intelligence.llm.providers.gemini_provider import GeminiProvider
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted, RateLimitKind


def _load_gemini_provider_row(session):
    from models.llm_provider import LlmProvider
    row = (
        session.query(LlmProvider)
        .filter(LlmProvider.is_active.is_(True), LlmProvider.type == "llm", LlmProvider.name == "gemini")
        .order_by(LlmProvider.priority)
        .first()
    )
    if row is None:
        raise SystemExit("No active 'gemini' row found in llm_providers — check the DB.")
    return row


def main() -> None:
    init_db()
    session = get_session()
    try:
        row = _load_gemini_provider_row(session)
        row_name, row_model, row_rpm, row_tpm, row_rpd, row_api_key_env = (
            row.name, row.model, row.rpm, row.tpm, row.rpd, row.api_key_env,
        )
    finally:
        session.close()

    api_key = os.environ.get(row_api_key_env)
    if not api_key:
        raise SystemExit(f"{row_api_key_env} not set in the environment (check .env).")

    print(f"Provider row: name={row_name} model={row_model} rpm={row_rpm} tpm={row_tpm} rpd={row_rpd}")
    if not row_rpm:
        raise SystemExit("This provider row has no rpm configured — nothing to exceed.")

    provider = GeminiProvider(api_key=api_key, model=row_model)

    # ── Phase 1: hammer _generate() directly — bypasses BaseProvider's tenacity
    # retry AND SlidingWindowStrategy, so we see the raw SDK exception the
    # instant Google returns a 429, un-obscured by our own retry/backoff. ─────
    calls_to_make = row_rpm + 5
    print(f"\nPhase 1: firing up to {calls_to_make} rapid calls (rpm={row_rpm}) with no delay...")

    first_429: Optional[Exception] = None
    successes = 0
    for i in range(1, calls_to_make + 1):
        try:
            provider._generate("", "Reply with exactly the word OK and nothing else.")
            successes += 1
            print(f"  call {i}: OK")
        except Exception as e:
            code = getattr(e, "code", None)
            print(f"  call {i}: {type(e).__name__} (code={code}) — {e}")
            if code == 429:
                first_429 = e
                break
            # Anything else (transient network blip, etc.) — keep hammering.

    if first_429 is None:
        print(
            f"\nNever hit a 429 after {calls_to_make} calls (rpm={row_rpm} wasn't actually exceeded — "
            f"maybe the account tier is higher than the DB row claims). Nothing to verify."
        )
        return

    classification = provider._classify_rate_limit(first_429)
    print(
        f"\nRaw exception: type={type(first_429).__name__} "
        f"code={getattr(first_429, 'code', None)} status={getattr(first_429, 'status', None)} "
        f"details={getattr(first_429, 'details', None)}"
    )
    print(f"_classify_rate_limit() returned: {classification}")

    if classification is RateLimitKind.RPD:
        print(
            "\n[WARN] Classified as RPD — BaseProvider would abort immediately instead of "
            "retrying, which is wrong for a plain RPM 429. Investigate the quota-id heuristic."
        )
        return
    elif classification is None:
        print(
            "\n[WARN] Not classified as a rate limit at all — BaseProvider would treat this as "
            "a generic failure, not retry-vs-abort correctly."
        )
    else:
        print(f"\n[OK] Classified as {classification.name} — BaseProvider should retry this, not abort.")

    # ── Phase 2: go through the real public API (tenacity retry + escalate) to
    # confirm it backs off and recovers instead of raising RateLimitExhausted. ─
    print(
        "\nPhase 2: calling provider.generate() through the full retry path "
        "(should back off and recover within the RPM window)..."
    )
    t0 = time.monotonic()
    try:
        result = provider.generate("Reply with exactly the word OK and nothing else.")
        elapsed = time.monotonic() - t0
        if result:
            print(f"[OK] Recovered after {elapsed:.1f}s — result: {result!r}")
        else:
            print(
                f"[WARN] generate() returned None after {elapsed:.1f}s (retries exhausted without "
                f"a rate-limit-classified error — check the log lines above)."
            )
    except RateLimitExhausted as e:
        elapsed = time.monotonic() - t0
        print(f"[FAIL] generate() raised RateLimitExhausted after {elapsed:.1f}s instead of retrying: {e}")


if __name__ == "__main__":
    main()
