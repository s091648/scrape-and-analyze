import json
from typing import Optional

import anthropic
from anthropic import RateLimitError

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .async_base_provider import AsyncBaseProvider

logger = get_logger(__name__)

# Mirrors ClaudeProvider's classification exactly — see that module's
# docstring for why Anthropic 429s are bucketed by Retry-After length rather
# than a true RPD signal.
_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


class AsyncClaudeProvider(AsyncBaseProvider):
    """024-async-pipeline-refactor: async sibling of ClaudeProvider (untouched
    — still used by the shared, out-of-scope build_llm_service()). Uses
    anthropic.AsyncAnthropic instead of anthropic.Anthropic."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        if not isinstance(exc, RateLimitError):
            return None
        retry_after = None
        if exc.response is not None:
            header = exc.response.headers.get("retry-after")
            try:
                retry_after = float(header) if header is not None else None
            except ValueError:
                retry_after = None
        if retry_after is not None and retry_after <= _SHORT_WAIT_THRESHOLD_SECONDS:
            return RateLimitKind.RPM
        return RateLimitKind.RPD

    async def _create_message(self, content: str, prompt: str):
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}],
        )

    async def _call_api(self, content: str, prompt: str) -> dict:
        response = await self._create_message(content, prompt)
        result = json.loads(response.content[0].text)
        result["_input_tokens"] = response.usage.input_tokens
        result["_output_tokens"] = response.usage.output_tokens
        logger.info("claude_api_called", model=self._model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens)
        return result

    async def _call_api_raw(self, content: str, prompt: str) -> str:
        response = await self._create_message(content, prompt)
        logger.info("claude_api_called_raw", model=self._model)
        return response.content[0].text
