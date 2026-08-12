import json
from typing import Optional

import requests

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .base_provider import BaseProvider

logger = get_logger(__name__)

_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter aggregates multiple upstream model providers, so a 429 can mean
# its own per-key rate limit or an exhausted upstream/account credit — we
# don't have a verified way to tell those apart from the response body, so
# fall back to the standard (RFC 7231) Retry-After header: short → retry
# (RPM), long or absent → treat as not worth retrying this run (RPD).
_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


class OpenRouterProvider(BaseProvider):
    """OpenRouter LLM provider implementing the BaseProvider interface via chat completions API."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._api_key = api_key

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        """Classify a 429 by the standard Retry-After header — see module docstring."""
        if not isinstance(exc, requests.exceptions.HTTPError):
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

    def _post(self, content: str, prompt: str) -> dict:
        """POST to OpenRouter chat completions endpoint and return the JSON response dict."""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        response = requests.post(
            _API_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": full_prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _call_api(self, content: str, prompt: str) -> dict:
        """Call OpenRouter API, parse JSON from message content, attach token usage."""
        data = self._post(content, prompt)
        result = json.loads(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        result["_input_tokens"] = usage.get("prompt_tokens", 0)
        result["_output_tokens"] = usage.get("completion_tokens", 0)
        logger.info("openrouter_api_called", model=self._model)
        return result

    def _call_api_raw(self, content: str, prompt: str) -> str:
        """Call OpenRouter API and return the raw message content text."""
        data = self._post(content, prompt)
        logger.info("openrouter_api_called_raw", model=self._model)
        return data["choices"][0]["message"]["content"]
