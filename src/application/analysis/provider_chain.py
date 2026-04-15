from dataclasses import dataclass
from typing import Optional, List

from src.analysis.providers import LLMProvider, AnalysisResult
from src.analysis.strategies import RequestStrategy, RateLimitExhausted
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderHandler:
    """
    Bridge: pairs one LLMProvider (what to call) with one RequestStrategy (how to throttle).
    """
    provider: LLMProvider
    strategy: RequestStrategy
    priority: int
    name: str

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
        self.strategy.acquire(estimated_tokens=len(content) // 4)
        result = self.provider.analyze(content, prompt)
        if result is not None:
            self.strategy.record_usage(result.input_tokens + result.output_tokens)
        return result


class ProviderChain(LLMProvider):
    """
    Composite: implements LLMProvider, holds an ordered list of ProviderHandlers.
    Walks handlers by priority; falls back to the next on any failure.
    """

    def __init__(self, handlers: List[ProviderHandler]) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)

    def analyze(self, content: str, prompt: str) -> Optional[AnalysisResult]:
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
