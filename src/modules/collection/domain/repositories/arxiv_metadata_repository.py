from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.modules.collection.domain.entities import ArxivMetadata


class ArxivMetadataRepository(ABC):

    @abstractmethod
    def save(self, meta: ArxivMetadata) -> ArxivMetadata:
        """Persist a new ArxivMetadata row. Returns saved entity with id populated."""

    @abstractmethod
    def find_by_article_id(self, article_id: UUID) -> Optional[ArxivMetadata]:
        """Return ArxivMetadata for this article, or None."""
