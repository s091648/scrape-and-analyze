import json
from typing import Optional

from google import genai
from google.genai.errors import ClientError

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .base_provider import BaseProvider

logger = get_logger(__name__)

_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


def _extract_retry_delay_seconds(details) -> Optional[float]:
    """Extract google.rpc.RetryInfo.retryDelay (e.g. "26s" -> 26.0) from a
    ClientError.details body. CONFIRMED against a real 429 from the Gemini
    API (scripts/verify_gemini_rate_limit_classification.py, 2026-08-12):
    the error is nested as details["error"]["details"][i] where that item's
    "@type" ends in "RetryInfo". Google does NOT set a Retry-After header on
    this call path — this JSON field is the actual signal, not a guess."""
    if not isinstance(details, dict):
        return None
    error_body = details.get("error", details)
    if not isinstance(error_body, dict):
        return None
    for item in error_body.get("details") or []:
        if not isinstance(item, dict):
            continue
        if not str(item.get("@type", "")).endswith("RetryInfo"):
            continue
        delay = item.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


class GeminiProvider(BaseProvider):
    """Google Gemini LLM provider implementing the BaseProvider interface."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = genai.Client(api_key=api_key, http_options={"timeout": 120_000})

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        """google-genai raises a typed ClientError on 4xx (errors.py) with `.code`
        (int status), `.status` (parsed gRPC-style status string, e.g.
        "RESOURCE_EXHAUSTED"), `.response` (raw httpx.Response), and `.details`
        (parsed JSON error body) — same shape of information as
        anthropic.RateLimitError, not a bare string to grep.

        Primary signal is google.rpc.RetryInfo.retryDelay in `.details` — a
        real 429 observed against this account (quotaId "...PerDay...") still
        carried `retryDelay: "26s"`, i.e. the quota clears far sooner than the
        "PerDay" name implies (a rolling/leaky-bucket quota, not a hard
        midnight reset) — trust what Google says to wait, not the quota-id
        label. Falls back to the quota-id naming convention only when no
        RetryInfo is present."""
        if not isinstance(exc, ClientError) or exc.code != 429:
            return None

        retry_delay = _extract_retry_delay_seconds(exc.details)
        if retry_delay is None and exc.response is not None:
            header = exc.response.headers.get("retry-after")
            try:
                retry_delay = float(header) if header is not None else None
            except ValueError:
                retry_delay = None
        if retry_delay is not None:
            return RateLimitKind.RPM if retry_delay <= _SHORT_WAIT_THRESHOLD_SECONDS else RateLimitKind.RPD

        if exc.status != "RESOURCE_EXHAUSTED":
            return None
        quota_id = str(exc.details)
        if "PerDay" in quota_id:
            return RateLimitKind.RPD
        if "Token" in quota_id:
            return RateLimitKind.TPM
        return RateLimitKind.RPM

    def _generate(self, content: str, prompt: str):
        """Send a generate_content request to Gemini and return the raw response.
        Raises the raw SDK exception on failure — BaseProvider classifies it via
        _classify_rate_limit() to decide retry (RPM/TPM) vs. abort (RPD)."""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return self._client.models.generate_content(
            model=self._model,
            contents=full_prompt,
        )

    def _call_api(self, content: str, prompt: str) -> dict:
        """Call Gemini API, strip markdown fences, parse JSON, and attach token usage."""
        response = self._generate(content, prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3].strip()
        result = json.loads(text)
        usage = getattr(response, "usage_metadata", None)
        result["_input_tokens"] = getattr(usage, "prompt_token_count", 0) if usage else 0
        result["_output_tokens"] = getattr(usage, "candidates_token_count", 0) if usage else 0
        logger.info("gemini_api_called", model=self._model)
        return result

    def _call_api_raw(self, content: str, prompt: str) -> str:
        """Call Gemini API and return raw text, returning empty string if blocked."""
        response = self._generate(content, prompt)
        if not response.candidates:
            return ""
        candidate = response.candidates[0]
        fr = candidate.finish_reason
        # fr is either an int or a FinishReason enum — accept both
        fr_name = fr.name if hasattr(fr, "name") else str(fr)
        if fr_name not in ("STOP", "1"):
            logger.warning("gemini_blocked", model=self._model, finish_reason=fr_name)
            return ""
        logger.info("gemini_api_called_raw", model=self._model)
        return (response.text or "").strip()