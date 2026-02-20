## Context

The system uses `ThreadPoolExecutor` (max_workers=3) in `src/main.py` to analyze articles concurrently. Each worker calls `analyzer.analyze()` directly on the same `LLMProvider` instance. When `LLM_PROVIDER=gemini` with the Free tier, three simultaneous API calls are dispatched without any coordination, reliably breaching the 5 RPM limit and triggering HTTP 429 errors.

The current `build_analyzer()` factory in `src/analyzers/__init__.py` returns a bare provider (`ClaudeProvider` or `GeminiProvider`) with no request coordination layer. The providers' `@retry` decorators handle transient failures but do not prevent the concurrent calls that cause rate limiting in the first place.

**Current flow (broken for Gemini Free):**
```
ThreadPoolExecutor (3 workers)
  Worker 1 → GeminiProvider.analyze()  ─┐
  Worker 2 → GeminiProvider.analyze()  ─┤─ all simultaneous → 429
  Worker 3 → GeminiProvider.analyze()  ─┘
```

**Known rate limits (Gemini Free tier):**
| Limit | Value | Implication |
|-------|-------|-------------|
| RPM   | 5     | minimum 12 seconds between requests |
| TPM   | 250K  | not a bottleneck for our article sizes |
| RPD   | 20    | hard cap; exceeding means silent failure until next day |

## Goals / Non-Goals

**Goals:**
- Eliminate HTTP 429 failures for Gemini Free tier in the current Railway deployment
- Make request behaviour configurable via `LLM_PROVIDER` + `LLM_API_TIER` env var combination
- Preserve the existing `LLMProvider` interface — callers in `src/main.py` require no changes
- Respect the RPD=20 daily cap and gracefully defer excess articles to the next run via `FailedTask`
- Preserve observability of permanent configuration errors (auth, invalid model) by not suppressing non-rate-limit exceptions

**Non-Goals:**
- Distributed rate limiting across multiple processes or deployments (single-process Cron Job is sufficient)
- Token-budget awareness (TPM tracking is not required for current article sizes)
- Dynamic rate limit discovery from API response headers
- Changing the concurrency model in `src/main.py` (ThreadPoolExecutor stays at max_workers=3)

## Decisions

### D1: Decorator pattern — strategy wraps the provider, not the caller

**Decision:**
Introduce a `RequestStrategy` layer that wraps an `LLMProvider` and itself implements the `LLMProvider` interface. `build_analyzer()` in `src/analyzers/__init__.py` returns the wrapped provider. All call sites (`analyze_article()`, `run_remediate()`) are unaffected.

```
build_analyzer()
  → creates provider (ClaudeProvider or GeminiProvider)
  → wraps it: build_strategy(provider, tier)  ← new step
  → returns wrapper (still typed as LLMProvider)
```

**Rationale:**
The Decorator pattern isolates the throttling concern from both the providers and the caller. Providers (`src/analyzers/claude.py`, `src/analyzers/gemini.py`) remain unchanged. `src/main.py` requires no structural changes. The strategy is transparent to the rest of the system.

Alternative considered: modifying `ThreadPoolExecutor` to use `max_workers=1` for free tier. Rejected because it conflates concurrency control with rate limiting and is less composable.

### D2: Strategy selection by (LLM_PROVIDER, LLM_API_TIER) — mapping and factory live in `strategy.py`

**Decision:**
The routing table and factory function both live in `src/analyzers/strategy.py`. The factory signature is `build_strategy(provider: LLMProvider, tier: str) -> LLMProvider`. The provider name is derived internally from `type(provider).__name__`, so callers do not pass a redundant name argument.

`build_analyzer()` in `src/analyzers/__init__.py` remains a simple factory: construct provider → call `build_strategy(provider, tier)` → return result. No routing logic in `__init__.py`.

| Condition | Strategy |
|-----------|----------|
| `isinstance(provider, GeminiProvider)` AND `tier == "free"` | `SequentialThrottleStrategy` |
| `isinstance(provider, GeminiProvider)` AND `tier == "paid"` | `UnthrottledStrategy` |
| `isinstance(provider, ClaudeProvider)` (any tier) | `UnthrottledStrategy` |
| Any other combination | `UnthrottledStrategy` (safe fallback; logs a WARNING for unrecognised tier values on rate-limited providers) |

**Rationale:**
Deriving the provider name internally avoids a caller error where the name and the instance could be mismatched. Keeping the routing table in `strategy.py` coheres it with the strategy implementations. The fallback warning (as opposed to silent fallback) surfaces operator typos (e.g., `LLM_API_TIER=fere`) before they cause 429 failures.

### D3: Thread-safe rate enforcement — context manager lock, injectable interval, one-shot warning, and correct timestamp on 429

**Decision:**
`SequentialThrottleStrategy` uses `with self._lock:` (Python context manager) to serialize all `analyze()` calls. The context manager guarantees the lock is released on every exit path — normal return, planned `None`, caught 429, and re-raised exception — eliminating any deadlock risk from manual acquire/release.

The constructor accepts `min_interval_seconds: float` (default: `60 / RPM`, e.g. `12.0` for Gemini Free 5 RPM) so the value can be injected during testing.

The strategy tracks four pieces of mutable state, all guarded by the lock:
- `_request_count: int` — number of completed delegations this process lifetime
- `_last_request_time: float` — timestamp captured at the **start** of the last delegation attempt (not at completion), enabling Start-to-Start interval measurement; initialized to `0.0`
- `_limit_logged: bool` — whether the run-limit warning has already been emitted; initialized to `False`

Three outcome categories:

| Outcome | Trigger | Action |
|---------|---------|--------|
| **Planned None** | `_request_count >= max_requests_per_run` | if not `_limit_logged`: log WARNING `event="llm_run_limit_reached"` and set `_limit_logged = True`; return `None` |
| **Transient None** | inner provider raises HTTP 429 | update `_last_request_time = now`; log WARNING; return `None` |
| **Exception (propagated)** | inner provider raises anything other than 429 | re-raise; lock released automatically by context manager |

**Control flow for `SequentialThrottleStrategy.analyze()`:**
```
with self._lock:
    now = time.time()                                          # (A) capture at entry — Start-to-Start timing

    if _request_count >= max_requests_per_run:                 # (B) check run cap first
        if not _limit_logged:
            log WARNING event="llm_run_limit_reached"
            _limit_logged = True
        return None                                            # lock released by context manager

    sleep_duration = max(0.0, min_interval_seconds - (now - _last_request_time))
    if sleep_duration > 0:                                     # (C) enforce interval
        log INFO "Throttling: sleeping for {sleep_duration:.1f}s to respect RPM"
        time.sleep(sleep_duration)

    _last_request_time = now                                   # (D) record start time BEFORE delegation

    try:
        result = _inner_provider.analyze(content, prompt)     # (E) delegate
    except HTTP429Error:
        log WARNING "429 received despite throttling; deferring article"
        return None                                            # lock released; _last_request_time already updated at (D)
    # any other exception: re-raise here; lock released automatically

    _request_count += 1                                        # (F) count only on success
    return result
```

**Rationale — context manager (deadlock fix):**
The v2 design described explicit `release lock` steps at each return site, but omitted a release on the non-429 re-raise path. A `with self._lock:` block is immune to this omission: Python releases the lock when the block exits, regardless of whether that exit is via `return`, raised exception, or fall-through. No manual release call is ever needed or safe to add.

**Rationale — `_last_request_time` updated before delegation (hammering fix):**
In the v2 design, `_last_request_time` was updated at step (F) — after a successful delegation. On a 429, step (F) was skipped, leaving `_last_request_time` at its previous value. The next waiting thread would then compute `sleep_duration = min_interval - (now - old_timestamp) ≈ 0`, meaning it would immediately re-hit the API. By updating `_last_request_time = now` at step (D) — before the delegation attempt — both the 429 path and the success path leave `_last_request_time` set to the start of the most recent attempt, ensuring the next thread always waits the full `min_interval_seconds`.

**Rationale — Start-to-Start timing:**
Capturing `now` at entry (A) and using it for both the sleep calculation and the `_last_request_time` update (D) implements Start-to-Start timing: the interval is measured from when the current request *started*, not when it *completed*. This is the correct model for an RPM limit, which is defined as requests-per-minute regardless of individual request duration.

**Rationale — one-shot warning:**
Without `_limit_logged`, a batch of 100 articles against a 20-request cap emits 80 identical warnings. The flag ensures the `llm_run_limit_reached` warning fires exactly once per process lifetime, preventing log spam and false alerts.

Alternative considered: returning a typed result object (`ThrottledResult | LimitResult | AnalysisResult`). Rejected because it breaks the `LLMProvider` interface and requires callers to change.

### D4: Configurable run request cap via `LLM_MAX_REQUESTS_PER_RUN`, with invalid-value guard

**Decision:**
The per-run request cap defaults to 20 (Gemini Free RPD) but is overridable via `LLM_MAX_REQUESTS_PER_RUN`. `src/config.py` exposes this as `LLM_MAX_REQUESTS_PER_RUN: int`, defaulting to `20`.

If `LLM_MAX_REQUESTS_PER_RUN <= 0`, the strategy constructor logs a WARNING at initialization (e.g., `LLM_MAX_REQUESTS_PER_RUN={value} is invalid (<= 0); all requests will be blocked`) and treats the cap as effectively 0 — every `analyze()` call returns `None` immediately. This surfaces misconfiguration rather than silently blocking all analysis.

**Rationale:**
An env var of `0` or `-1` set by mistake would block all analysis silently. An explicit log at startup makes the error visible in Railway logs without requiring a code deployment to diagnose.

### D5: Module location and interface contract

**Decision:**
- New file: `src/analyzers/strategy.py` — `RequestStrategy` ABC, `UnthrottledStrategy`, `SequentialThrottleStrategy`, and `build_strategy()` factory
- `src/analyzers/__init__.py` — updated `build_analyzer()`: construct provider → `build_strategy(provider, tier)` → return result; emits INFO log with `llm_provider`, `llm_api_tier`, `strategy` fields
- `src/config.py` — adds `LLM_API_TIER` (default `"free"`) and `LLM_MAX_REQUESTS_PER_RUN` (default `20`)

**Interface contract (behaviour, not code):**
- Both strategies implement `LLMProvider` — they expose `analyze(content, prompt) -> Optional[AnalysisResult]`
- `UnthrottledStrategy.analyze()` delegates immediately with no side effects; propagates all return values and exceptions unchanged
- `SequentialThrottleStrategy.analyze()` may block the calling thread (up to `min_interval_seconds`); returns `None` for planned run-cap or 429 outcomes; re-raises all other provider exceptions; the lock is **always** released via context manager
- Strategy instances are shared across threads; internal state is fully guarded by `self._lock`

## Testing

The following test cases are required. Implementation MUST NOT proceed until these are verifiable.

### T1 — Unit: `min_interval` sleep calculation (Start-to-Start timing)

**What is tested:** `SequentialThrottleStrategy` computes and sleeps the correct remaining duration.

**Method:** Construct strategy with `min_interval_seconds=12`. Mock `time.time`.
- First call: `now=0.0`. Set `_last_request_time=0.0`. No prior call, no sleep.
- Second call: `now=103.5`; elapsed = 103.5 - 0.0 = 103.5s > 12s → no sleep.
- Third call: `now=100.0` (simulate thread entering just after second call started); `_last_request_time=103.5` → elapsed = 100 - 103.5 = -3.5 → `sleep_duration = max(0, 12 - (-3.5))` = capped by the scenario; adjust scenario: `_last_request_time=100.0`, `now=103.5` → elapsed = 3.5s → `sleep(12 - 3.5 = 8.5)`.

**Assert:** `time.sleep` is called with `pytest.approx(8.5, abs=0.01)`.

---

### T2 — Concurrency: sequential execution verified without real delays

**What is tested:** Three concurrent calls execute sequentially, not in parallel.

**Method:** Construct strategy with `min_interval_seconds=0.1`. Spawn 3 threads, each calling `strategy.analyze()` simultaneously. Mock the inner provider to return immediately.

**Assert:**
- Total wall-clock time ≥ `(3 - 1) × 0.1s = 0.2s` (proves serial execution).
- Total wall-clock time < `5s` (proves the real 12s interval is not in use).
- Inner provider called exactly 3 times; no two calls overlap.

---

### T3 — Boundary: run cap returns None and warning logged exactly once

**What is tested:** Cap enforcement and one-shot warning behaviour.

**Method:** Construct strategy with `max_requests_per_run=2`, `min_interval_seconds=0`. Call `analyze()` five times sequentially with a mocked provider.

**Assert:**
- Calls 1–2: inner provider invoked; result returned.
- Call 3: inner provider NOT invoked; `None` returned; `event="llm_run_limit_reached"` WARNING emitted once.
- Calls 4–5: inner provider NOT invoked; `None` returned; no additional `llm_run_limit_reached` entries (total log count = 1).

---

### T4 — Lock safety: non-429 exception does not deadlock

**What is tested:** The lock is released even when a non-429 exception propagates.

**Method:** Construct strategy with `min_interval_seconds=0`. Mock inner provider to raise `AuthenticationError` (status 401). Call `analyze()` once, catching the exception. Then call `analyze()` a second time (succeeds with mocked result).

**Assert:**
- First call raises `AuthenticationError`.
- Second call succeeds (proves the lock was released; deadlock would cause the second call to hang indefinitely).

---

### T5 — Error differentiation: 429 updates timestamp and returns None

**What is tested:** A 429 from the inner provider returns `None` AND updates `_last_request_time` so the next call respects the interval.

**Method:** Construct strategy with `min_interval_seconds=0.1`. Mock inner provider to raise `HTTPError(429)` on the first call and return a valid result on the second. Record wall-clock time between calls.

**Assert:**
- First call returns `None` without raising.
- Second call is delayed by approximately `min_interval_seconds` (proves `_last_request_time` was updated during the 429 path).
- Second call returns the mocked result.

---

### T6 — Config guard: LLM_MAX_REQUESTS_PER_RUN ≤ 0 blocks all and logs at init

**What is tested:** Invalid cap value is handled safely with a visible startup log.

**Method:** Construct strategy with `max_requests_per_run=0`.

**Assert:**
- A WARNING is emitted at construction time mentioning the invalid value.
- Every call to `analyze()` returns `None`; inner provider is never invoked.

## Risks / Trade-offs

**R1: Serialization reduces throughput for free tier**
Sequential execution with a 12-second inter-request delay means 20 articles take ~4 minutes minimum. This is acceptable given the 20 RPD cap — there is no benefit in parallelising if the daily budget is the binding constraint.

**R2: Per-process run counter is not persistent**
`_request_count` resets with each Cron Job execution. If the job is re-run manually in the same calendar day, it could exceed the 20 RPD limit at the API level. Mitigation: the API returns 429, which is caught and returned as `None` (see D3); the article lands in `FailedTask`. Acceptable for a side-project deployment.

**R3: Lock held during the entire network call (head-of-line blocking)**
The lock spans the provider's `analyze()` call, including any internal `@retry` attempts. A single hung or slow API call blocks all other worker threads — including those that would return `None` immediately due to the run cap. This is explicitly accepted for the current use case (max_workers=3, single-process Cron Job, 20 RPD). The provider HTTP client's own timeout is the safety net. If worker count grows significantly, the lock scope should be narrowed to only guard the slot assignment (timestamp + counter update), with sleep and delegation moved outside the lock.

**R4: Lock contention for non-free strategies is zero**
`UnthrottledStrategy` does not use a lock. No regression risk for Claude or paid Gemini deployments.

**R5: Silent deferral if run cap is hit mid-batch**
Articles after the cap return `None` and land in `failed_tasks`. They retry on the next daily run. The one-shot `llm_run_limit_reached` log makes this clearly visible in Railway logs without spam.

## Migration Plan

1. Add `LLM_API_TIER=free` and `LLM_MAX_REQUESTS_PER_RUN=20` to Railway environment variables
2. Deploy the new code — no schema changes, no data migration required
3. Verify next Cron Job run logs show `strategy=SequentialThrottleStrategy` and no 429 errors

Rollback: set `LLM_API_TIER=paid` in Railway env to revert to `UnthrottledStrategy` without a code deployment.

## Open Questions

- For future providers with known rate limits (e.g., OpenAI Free), should rate limit constants (RPM, RPD) live in `strategy.py` or in each provider file?
