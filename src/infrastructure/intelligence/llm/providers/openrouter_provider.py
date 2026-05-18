import json

import requests

from src.shared.logging import get_logger
from .base_provider import BaseProvider

logger = get_logger(__name__)

_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(BaseProvider):

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._api_key = api_key

    def _post(self, content: str, prompt: str) -> dict:
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
        data = self._post(content, prompt)
        result = json.loads(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        result["_input_tokens"] = usage.get("prompt_tokens", 0)
        result["_output_tokens"] = usage.get("completion_tokens", 0)
        logger.info("openrouter_api_called", model=self._model)
        return result

    def _call_api_raw(self, content: str, prompt: str) -> str:
        data = self._post(content, prompt)
        logger.info("openrouter_api_called_raw", model=self._model)
        return data["choices"][0]["message"]["content"]
