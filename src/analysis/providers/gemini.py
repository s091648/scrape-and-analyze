import json
from typing import Optional

from google import genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.analysis.providers.base_llm_provider import AnalysisResult, LLMProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)

_REQUIRED_FIELDS = ['tag_groups', 'pain_points', 'insights', 'innovations']


class GeminiProvider(LLMProvider):
    """LLM Provider using Google AI Studio's Gemini API"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(Exception)
    )
    def _call_api(self, content: str, prompt: str):
        """Call Gemini API with retry logic"""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"
        return self.client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
        )

    def _parse_response_text(self, text: str) -> dict:
        """Strip markdown code fences if present, then parse JSON"""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3].strip()
        return json.loads(text)

    def _validate_response(self, result_json: dict) -> bool:
        """Validate response has required fields with correct types"""
        if not all(field in result_json for field in _REQUIRED_FIELDS):
            logger.error("gemini_response_missing_fields",
                         expected=_REQUIRED_FIELDS,
                         actual=list(result_json.keys()))
            return False
        tag_groups = result_json.get('tag_groups')
        if not isinstance(tag_groups, list):
            logger.error("gemini_response_invalid_tag_groups",
                         type=type(tag_groups).__name__)
            return False
        for item in tag_groups:
            if not isinstance(item, dict) or 'group' not in item or 'tags' not in item:
                logger.error("gemini_response_malformed_tag_group", item=item)
                return False
            if not isinstance(item['tags'], list):
                return False
        return True

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Analyze content using Gemini API"""
        try:
            response = self._call_api(content, prompt)
        except Exception as e:
            logger.error("gemini_api_call_failed", error=str(e))
            return None

        try:
            result_json = self._parse_response_text(response.text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("gemini_response_parse_failed", error=str(e))
            return None

        if not self._validate_response(result_json):
            return None

        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count
        output_tokens = usage.candidates_token_count

        logger.info("llm_analysis_completed",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens)

        return AnalysisResult(
            tag_groups=result_json.get('tag_groups', []),
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_used=self.model_name,
        )
