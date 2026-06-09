from abc import ABC, abstractmethod
from typing import List

import tenacity

from src.modules.intelligence.domain.services import EmbeddingService
from src.shared.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 100


def _is_retryable(exc: BaseException) -> bool:
    """Retry on transient API / network errors."""
    return True


class BaseEmbeddingProvider(EmbeddingService, ABC):
    """
    Infrastructure base for all embedding providers.

    Implements EmbeddingService.embed() and embed_batch() as templates:
      1. Split into chunks of _BATCH_SIZE.
      2. Call _call_embed() with exponential-backoff retry per chunk.
      3. Assemble and return results.

    Subclasses implement only _call_embed() — retry and batching are handled here.
    """

    def __init__(self, model: str) -> None:
        self._model = model
        self._retry = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_is_retryable),
            wait=tenacity.wait_exponential(multiplier=1, min=4, max=60),
            stop=tenacity.stop_after_attempt(3),
            reraise=True,
        )

    @abstractmethod
    def _call_embed(self, texts: List[str]) -> List[List[float]]:
        """
        Call the provider API with a batch of texts and return one vector per text.
        Raise on any failure — retry is handled by the base class.
        """
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate tokens for a given text, used for rate limit estimation."""
        ...

    def embed(self, text: str) -> List[float]:
        """Embed a single text string and return its vector."""
        for attempt in self._retry:
            with attempt:
                result = self._call_embed([text])
        return result[0]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts in chunks, with retry per chunk."""
        results: List[List[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            chunk = texts[i : i + _BATCH_SIZE]
            for attempt in self._retry:
                with attempt:
                    chunk_results = self._call_embed(chunk)
            results.extend(chunk_results)
            logger.debug("embedding_chunk_done", model=self._model, count=len(chunk))
        return results
