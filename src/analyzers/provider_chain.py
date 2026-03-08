from dataclasses import dataclass
from typing import Optional, List

from src.analyzers.llm_provider import LLMProvider, AnalysisResult
from src.analyzers.request_strategy import RequestStrategy, RateLimitExhausted
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
