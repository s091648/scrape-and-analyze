import json

import anthropic

from src.shared.logging import get_logger
from .base_provider import BaseProvider

logger = get_logger(__name__)


class ClaudeProvider(BaseProvider):

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = anthropic.Anthropic(api_key=api_key)

    def _create_message(self, content: str, prompt: str):
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}],
        )

    def _call_api(self, content: str, prompt: str) -> dict:
        response = self._create_message(content, prompt)
        result = json.loads(response.content[0].text)
        result["_input_tokens"] = response.usage.input_tokens
        result["_output_tokens"] = response.usage.output_tokens
        logger.info("claude_api_called", model=self._model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens)
        return result

    def _call_api_raw(self, content: str, prompt: str) -> str:
        response = self._create_message(content, prompt)
        logger.info("claude_api_called_raw", model=self._model)
        return response.content[0].text
