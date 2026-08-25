import json
from typing import Optional

from google import genai
from google.genai.errors import ClientError

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .async_base_provider import AsyncBaseProvider
from .gemini_provider import _extract_retry_delay_seconds

logger = get_logger(__name__)

_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


class AsyncGeminiProvider(AsyncBaseProvider):
    """024-async-pipeline-refactor: async sibling of GeminiProvider (untouched
    — still used by the shared, out-of-scope build_llm_service()). Same
    genai.Client, called through its `.aio` namespace instead of directly —
    the google-genai SDK exposes both sync and async methods on one client
    instance, so construction is unchanged. Reuses
    _extract_retry_delay_seconds directly from gemini_provider.py (pure
    function, no sync/async-specific state)."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = genai.Client(api_key=api_key, http_options={"timeout": 120_000})

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        """See GeminiProvider._classify_rate_limit for the full rationale —
        identical logic, duplicated rather than imported because it reads
        `self`-free but is defined as an instance method there."""
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

    async def _generate(self, content: str, prompt: str):
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return await self._client.aio.models.generate_content(
            model=self._model,
            contents=full_prompt,
        )

    async def _call_api(self, content: str, prompt: str) -> dict:
        response = await self._generate(content, prompt)
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

    async def _call_api_raw(self, content: str, prompt: str) -> str:
        response = await self._generate(content, prompt)
        if not response.candidates:
            return ""
        candidate = response.candidates[0]
        fr = candidate.finish_reason
        fr_name = fr.name if hasattr(fr, "name") else str(fr)
        if fr_name not in ("STOP", "1"):
            logger.warning("gemini_blocked", model=self._model, finish_reason=fr_name)
            return ""
        logger.info("gemini_api_called_raw", model=self._model)
        return (response.text or "").strip()
