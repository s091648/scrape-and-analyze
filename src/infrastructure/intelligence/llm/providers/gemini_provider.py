import json

from google import genai

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted
from .base_provider import BaseProvider

logger = get_logger(__name__)


class GeminiProvider(BaseProvider):

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__(model=model)
        self._client = genai.Client(api_key=api_key)

    def _call_api(self, content: str, prompt: str) -> dict:
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=full_prompt,
            )
        except Exception as e:
            error_str = str(e)
            if "RESOURCE_EXHAUSTED" in error_str and "PerDay" in error_str:
                raise RateLimitExhausted(f"Daily quota exceeded for {self._model}") from e
            raise
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
