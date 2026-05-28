from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.shared.logging import get_logger
from src.modules.intelligence.domain.services import LLMService, EmbeddingService
from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata
from src.infrastructure.intelligence.llm.embedding import BaseEmbeddingProvider
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

###
### Single-thread for-now.
### Would need to add locking in handlers when moving rate-limited providers
### to the end of the list to avoid race conditions.
###
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

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.analyze(content, prompt)

                if result is not None:
                    return result

                logger.warning(
                    "provider_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                logger.warning(
                    "provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_providers_exhausted")
        return None

    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.translate(content, prompt)

                if result is not None:
                    return result

                logger.warning(
                    "provider_translate_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                logger.warning(
                    "provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "provider_translate_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_providers_exhausted_translate")
        return None


@dataclass
class EmbeddingProviderHandler:
    """
    Wraps any EmbeddingService with quota management — mirrors the
    acquire → call → record_usage pattern used by ProviderHandler in the LLM stack.
    """
    provider: BaseEmbeddingProvider
    strategy: QuotaStrategy
    priority: int
    name: str
    _can_count_tokens: bool = True

    def embed(self, text: str) -> List[float]:
        self.strategy.update_batch_size(1)
        self.strategy.acquire(max(1, len(text) // 4))
        if self._can_count_tokens:
            try:
                token = self.provider.count_tokens(text)
            except Exception as e:
                logger.error("count_tokens_failed", provider=self.name, error=str(e))
                self._can_count_tokens = False
                token = len(text) // 4
        else:
            token = len(text) // 4
        result = self.provider.embed(text)
        if result is not None:
            self.strategy.record_usage(token)
        return result

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        estimated = max(1, sum(len(t) for t in texts) // 4)
        self.strategy.update_batch_size(len(texts))
        self.strategy.acquire(estimated)
        result = self.provider.embed_batch(texts)
        if result is not None:
            if self._can_count_tokens:
                try:
                    actual = self.provider.count_tokens(" ".join(texts))
                except Exception as e:
                    logger.error("count_tokens_failed", provider=self.name, error=str(e))
                    self._can_count_tokens = False
                    actual = estimated
            else:
                actual = estimated
            self.strategy.record_usage(actual)
        return result


class ResilientEmbeddingService(EmbeddingService):
    """
    Composite EmbeddingService that tries multiple providers in order.
    """

    def __init__(self, handlers: List[EmbeddingProviderHandler]) -> None:
        self._handlers = sorted(handlers, key=lambda h: h.priority)

    def embed(self, text: str) -> Optional[List[float]]:

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.embed(text)

                if result is not None:
                    return result

                logger.warning(
                    "embedding_provider_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                logger.warning(
                    "embedding_provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "embedding_provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "embedding_provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_embedding_providers_exhausted")
        return None

    def embed_batch(
        self,
        texts: List[str],
    ) -> Optional[List[List[float]]]:

        handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            try:
                result = handler.embed_batch(texts)

                if result is not None:
                    return result

                logger.warning(
                    "embedding_provider_batch_returned_none",
                    provider=handler.name,
                )

            except RateLimitExhausted:
                logger.warning(
                    "embedding_provider_daily_limit_reached",
                    provider=handler.name,
                )

                self._handlers.remove(handler)
                self._handlers.append(handler)

                logger.warning(
                    "embedding_provider_moved_to_end",
                    provider=handler.name,
                )

            except Exception as e:
                logger.error(
                    "embedding_provider_failed",
                    provider=handler.name,
                    error=str(e),
                )

        logger.error("all_embedding_providers_exhausted")
        return None