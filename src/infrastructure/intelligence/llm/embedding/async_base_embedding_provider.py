from abc import ABC, abstractmethod
from typing import List

import tenacity

from src.shared.logging import get_logger
from src.infrastructure.intelligence.llm.rate_limit import RateLimitExhausted

logger = get_logger(__name__)

_BATCH_SIZE = 100


def _is_retryable(exc: BaseException) -> bool:
    # RateLimitExhausted (daily quota) can't succeed on retry — retrying it just
    # delays the failover to the next provider that AsyncResilientEmbeddingService
    # would otherwise do immediately.
    return not isinstance(exc, RateLimitExhausted)


class AsyncBaseEmbeddingProvider(ABC):
    """024-async-pipeline-refactor: async sibling of BaseEmbeddingProvider
    (untouched — still used by the shared, out-of-scope build_llm_service()).
    Same template-method shape, tenacity.AsyncRetrying instead of Retrying."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._retry = tenacity.AsyncRetrying(
            retry=tenacity.retry_if_exception(_is_retryable),
            wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
            stop=tenacity.stop_after_attempt(3),
            reraise=True,
        )

    @abstractmethod
    async def _call_embed(self, texts: List[str]) -> List[List[float]]:
        """Call the provider API with a batch of texts and return one vector
        per text. Raise on any failure — retry is handled by the base class."""
        ...

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate tokens for a given text, used for rate limit estimation."""
        ...

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string and return its vector."""
        # 024-async-pipeline-refactor follow-up: AsyncRetrying holds mutable
        # per-attempt state — .copy() gives this call its own controller so
        # concurrent embed()/embed_batch() calls on the same provider instance
        # don't overwrite each other's retry state.
        async for attempt in self._retry.copy():
            with attempt:
                result = await self._call_embed([text])
        return result[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts in chunks, with retry per chunk."""
        results: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            chunk = texts[i : i + _BATCH_SIZE]
            async for attempt in self._retry.copy():
                with attempt:
                    chunk_results = await self._call_embed(chunk)
            results.extend(chunk_results)
            logger.debug("embedding_chunk_done", model=self._model, count=len(chunk))
        return results
