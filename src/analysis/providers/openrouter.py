import json
import requests
from typing import Optional

from src.analysis.providers.base_llm_provider import LLMProvider, AnalysisResult
from src.utils.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_FIELDS = ['tag_groups', 'pain_points', 'insights', 'innovations', 'summary']
_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(LLMProvider):
    """LLM Provider using OpenRouter's OpenAI-compatible API."""

    def __init__(self, api_key: str, model: str = "deepseek/deepseek-chat") -> None:
        self._api_key = api_key
        self._model = model

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        try:
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
        except Exception as e:
            logger.error("openrouter_api_call_failed", error=str(e))
            return None

        try:
            data = response.json()
            text = data['choices'][0]['message']['content']
            result_json = json.loads(text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error("openrouter_response_parse_failed", error=str(e))
            return None

        if not all(f in result_json for f in _REQUIRED_FIELDS):
            logger.error("openrouter_response_missing_fields",
                         actual=list(result_json.keys()))
            return None

        usage = data.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        logger.info("llm_analysis_completed", model=self._model,
                    input_tokens=input_tokens, output_tokens=output_tokens)

        return AnalysisResult(
            tag_groups=result_json.get('tag_groups', []),
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            summary=result_json.get('summary', ''),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_used=self._model,
        )
