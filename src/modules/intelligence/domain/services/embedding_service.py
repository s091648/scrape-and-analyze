from abc import ABC, abstractmethod
from typing import List


class EmbeddingService(ABC):
    """Domain interface for generating text embeddings for tag normalization."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return a 768-dimensional embedding vector for the given text."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Return embedding vectors for a list of texts (max 100 per call)."""
        ...
