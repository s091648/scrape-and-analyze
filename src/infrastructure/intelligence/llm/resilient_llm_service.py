from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.infrastructure.intelligence.llm.providers import BaseProvider
from src.infrastructure.intelligence.llm.rate_limit import QuotaStrategy, RateLimitExhausted

logger = get_logger(__name__)


@dataclass
class ProviderHandler:
    """Pairs a provider with its quota management strategy."""
    provider: BaseProvider
    strategy: QuotaStrategy
    priority: int
    name: str

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = self.provider.analyze(content, prompt)
        if result is not None:
            _, metadata = result
            self.strategy.record_usage(metadata.input_tokens + metadata.output_tokens)
        return result

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = self.provider.translate(content, prompt)
        if result is not None:
            self.strategy.record_usage(len(content) // 4 + len(result) // 4)
        return result


class ResilientLLMService(LLMService):
    """
    Composite LLMService that walks an ordered list of ProviderHandlers.
    Falls back to the next provider on rate limit or failure.
    """

    def __init__(self, handlers: List[ProviderHandler]) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)

    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        for handler in self._handlers:
            try:
                result = handler.analyze(content, prompt)
                if result is not None:
                    return result
                logger.warning("provider_returned_none", provider=handler.name)
            except RateLimitExhausted:
                logger.warning("provider_daily_limit_reached", provider=handler.name)
            except Exception as e:
                logger.error("provider_failed", provider=handler.name, error=str(e))

        logger.error("all_providers_exhausted")
        return None

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        for handler in self._handlers:
            try:
                result = handler.translate(content, prompt)
                if result is not None:
                    return result
                logger.warning("provider_translate_returned_none", provider=handler.name)
            except RateLimitExhausted:
                logger.warning("provider_daily_limit_reached", provider=handler.name)
            except Exception as e:
                logger.error("provider_translate_failed", provider=handler.name, error=str(e))

        logger.error("all_providers_exhausted_translate")
        return None
