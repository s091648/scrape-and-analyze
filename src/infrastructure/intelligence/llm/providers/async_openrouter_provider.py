import json
from typing import Optional

import httpx

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .async_base_provider import AsyncBaseProvider

logger = get_logger(__name__)

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


class AsyncOpenRouterProvider(AsyncBaseProvider):
    """024-async-pipeline-refactor: async sibling of OpenRouterProvider
    (untouched — still used by the shared, out-of-scope build_llm_service()).
    Uses httpx.AsyncClient instead of requests.post — opened and closed
    per-call (async with), matching the sync version's non-persistent style
    rather than holding a long-lived client across this provider's lifetime."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._api_key = api_key

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        """Classify a 429 by the standard Retry-After header — see
        OpenRouterProvider's module docstring."""
        if not isinstance(exc, httpx.HTTPStatusError):
            return None
        if exc.response is None or exc.response.status_code != 429:
            return None
        header = exc.response.headers.get("Retry-After")
        try:
            retry_after = float(header) if header is not None else None
        except ValueError:
            retry_after = None
        if retry_after is not None and retry_after <= _SHORT_WAIT_THRESHOLD_SECONDS:
            return RateLimitKind.RPM
        return RateLimitKind.RPD

    async def _post(self, content: str, prompt: str) -> dict:
        """POST to OpenRouter chat completions endpoint and return the JSON response dict."""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                _API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": full_prompt}],
                },
            )
        response.raise_for_status()
        return response.json()

    async def _call_api(self, content: str, prompt: str) -> dict:
        data = await self._post(content, prompt)
        result = json.loads(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        result["_input_tokens"] = usage.get("prompt_tokens", 0)
        result["_output_tokens"] = usage.get("completion_tokens", 0)
        logger.info("openrouter_api_called", model=self._model)
        return result

    async def _call_api_raw(self, content: str, prompt: str) -> str:
        data = await self._post(content, prompt)
        logger.info("openrouter_api_called_raw", model=self._model)
        return data["choices"][0]["message"]["content"]
