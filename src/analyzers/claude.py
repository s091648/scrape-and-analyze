import anthropic
import json
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.analyzers.llm_provider import LLMProvider, AnalysisResult
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeProvider(LLMProvider):
    """LLM Provider using Anthropic's Claude API"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(Exception)
    )
    def _call_api(self, content: str, prompt: str):
        """Call Claude API with retry logic"""
        full_prompt = f"{prompt}\n\n<article>\n{content}\n</article>"

        return self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": full_prompt}]
        )

    def _validate_response(self, result_json: dict) -> bool:
        """Validate LLM response has required fields with correct types"""
        required_fields = ['tags', 'pain_points', 'insights', 'innovations']

        if not all(field in result_json for field in required_fields):
            logger.error("claude_response_missing_fields",
                         expected=required_fields,
                         actual=list(result_json.keys()))
            return False

        if not isinstance(result_json.get('tags'), list):
            logger.error("claude_response_invalid_tags",
                         tags_type=type(result_json.get('tags')).__name__)
            return False

        return True

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        """Analyze content using Claude API"""
        try:
            response = self._call_api(content, prompt)
        except Exception as e:
            logger.error("claude_api_call_failed", error=str(e))
            return None

        try:
            response_text = response.content[0].text
            result_json = json.loads(response_text)
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error("claude_response_parse_failed", error=str(e))
            return None

        if not self._validate_response(result_json):
            return None

        logger.info("llm_analysis_completed",
                    model=self.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens)

        return AnalysisResult(
            tags=result_json.get('tags', []),
            pain_points=result_json.get('pain_points', ''),
            insights=result_json.get('insights', ''),
            innovations=result_json.get('innovations', ''),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
