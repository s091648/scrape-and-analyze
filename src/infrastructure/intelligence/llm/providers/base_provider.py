import json
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import tenacity

from src.shared.logging import get_logger
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata, TagGroup
from src.modules.intelligence.domain.services import LLMService
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

logger = get_logger(__name__)

_REQUIRED_FIELDS = ['tag_groups', 'pain_points', 'insights', 'innovations', 'summary']

# Errors that indicate a bad response format or bad request — retrying wastes quota.
_NON_RETRYABLE = (
    json.JSONDecodeError,
    ValueError,
    KeyError,
    IndexError,
    RateLimitExhausted,
)

# For translate(), only rate-limit and network are non-retryable.
_TRANSLATE_NON_RETRYABLE = (
    RateLimitExhausted,
)


def _to_str(val) -> str:
    """Coerce LLM output to str: join lists with newline, pass strings through."""
    if isinstance(val, list):
        return "\n".join(str(item) for item in val)
    return val or ""


def _is_retryable(exc: BaseException) -> bool:
    """Retry on transient API / network errors; never retry on parse failures."""
    return not isinstance(exc, _NON_RETRYABLE)


def _is_translate_retryable(exc: BaseException) -> bool:
    """For translate(), retry on most errors (no JSON parsing to fail on)."""
    return not isinstance(exc, _TRANSLATE_NON_RETRYABLE)


class BaseProvider(LLMService, ABC):
    """
    Infrastructure base for all LLM providers.

    Implements LLMService.analyze() as a template:
      1. Call _call_api() with exponential-backoff retry (transient errors only).
      2. Validate required fields in the JSON response.
      3. Map to domain value objects and return.

    Prompt is passed at analyze() call time — providers do NOT store a prompt.
    This allows each article to be analyzed with a topic-specific rendered prompt.
    Retry is centralised here; individual _call_api() implementations must NOT
    add their own @retry decorators.
    """

    def __init__(self, model: str) -> None:
        self._model = model
        self._retry = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_is_retryable),
            wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
            stop=tenacity.stop_after_attempt(3),
            reraise=True,
        )
        self._translate_retry = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_is_translate_retryable),
            wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
            stop=tenacity.stop_after_attempt(3),
            reraise=True,
        )

    @abstractmethod
    def _call_api(self, content: str, prompt: str) -> dict:
        """
        Call the provider API and return a parsed JSON dict.
        Raise on any failure — retry is handled by the base class.
        """
        ...

    @abstractmethod
    def _call_api_raw(self, content: str, prompt: str) -> Tuple[str, int, int]:
        """
        Call the provider API and return raw text response.
        Returns (text, input_tokens, output_tokens).
        Raise on any failure — retry is handled by the base class.
        """
        ...

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        try:
            for attempt in self._retry:
                with attempt:
                    result = self._call_api(content, prompt)
        except RateLimitExhausted:
            raise
        except Exception as e:
            logger.warning("provider_analyze_failed", model=self._model, error=str(e))
            return None

        if not self._validate(result):
            logger.warning("provider_response_invalid", model=self._model, keys=list(result.keys()))
            return None

        tag_groups = [
            TagGroup(
                display_name=tg.get("group", ""),
                description=", ".join(tg.get("tags", [])),
            )
            for tg in result.get("tag_groups", [])
        ]
        analysis_content = AnalysisContent(
            pain_points=_to_str(result.get("pain_points")),
            insights=_to_str(result.get("insights")),
            innovations=_to_str(result.get("innovations")),
            summary=_to_str(result.get("summary")),
            tag_groups=tag_groups,
        )
        analysis_metadata = AnalysisMetadata(
            model_used=self._model,
            input_tokens=result.get("_input_tokens", 0),
            output_tokens=result.get("_output_tokens", 0),
        )
        return analysis_content, analysis_metadata

    def _validate(self, result: dict) -> bool:
        return all(f in result for f in _REQUIRED_FIELDS)

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        try:
            for attempt in self._translate_retry:
                with attempt:
                    text, _, _ = self._call_api_raw(content, prompt)
        except RateLimitExhausted:
            raise
        except Exception as e:
            logger.warning("provider_translate_failed", model=self._model, error=str(e))
            return None

        if not text.strip():
            logger.warning("provider_translate_empty", model=self._model)
            return None

        return text