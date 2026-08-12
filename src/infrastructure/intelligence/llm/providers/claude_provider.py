import json
from typing import Optional

import anthropic
# Imported by name (not accessed as `anthropic.RateLimitError`) so this keeps
# resolving to the real exception class under tests that patch the module-level
# `anthropic` name (e.g. `patch("...claude_provider.anthropic")`) — see
# test_claude_provider.py, which relies on that patching style.
from anthropic import RateLimitError

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitKind
from .base_provider import BaseProvider

logger = get_logger(__name__)

# Anthropic doesn't have a fixed "requests-per-day" bucket the way Gemini's free
# tier does — RateLimitError is 429s from RPM/TPM/ITPM/OTPM tiers. We can't
# reliably tell those apart client-side (the SDK only confirms `retry-after` /
# `retry-after-ms` as parsed headers — see anthropic._base_client — not any
# `anthropic-ratelimit-*` header, which would need re-verifying against the
# installed SDK/API before relying on it). So RPD here really means "this
# provider isn't worth retrying within this run" rather than a literal daily
# cap: a short Retry-After is treated as RPM (retry), anything longer or
# absent is treated as RPD (abort for this run) since we have no basis to
# assume it'll clear before the run ends.
_SHORT_WAIT_THRESHOLD_SECONDS = 60.0


class ClaudeProvider(BaseProvider):
    """Anthropic Claude LLM provider implementing the BaseProvider interface."""

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = anthropic.Anthropic(api_key=api_key)

    def _classify_rate_limit(self, exc: BaseException) -> Optional[RateLimitKind]:
        """Classify a 429 by how long the API says to wait — see module docstring
        for why this doesn't distinguish RPM from TPM."""
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

    def _create_message(self, content: str, prompt: str):
        """Send a message to the Claude API and return the raw response object."""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}],
        )

    def _call_api(self, content: str, prompt: str) -> dict:
        """Call Claude API, parse JSON response, and attach token usage metadata."""
        response = self._create_message(content, prompt)
        result = json.loads(response.content[0].text)
        result["_input_tokens"] = response.usage.input_tokens
        result["_output_tokens"] = response.usage.output_tokens
        logger.info("claude_api_called", model=self._model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens)
        return result

    def _call_api_raw(self, content: str, prompt: str) -> str:
        """Call Claude API and return the raw text response without JSON parsing."""
        response = self._create_message(content, prompt)
        logger.info("claude_api_called_raw", model=self._model)
        return response.content[0].text
