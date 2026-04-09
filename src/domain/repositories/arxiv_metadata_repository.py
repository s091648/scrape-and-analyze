from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.domain.entities.arxiv_metadata import ArxivMetadataEntity


class ArxivMetadataRepository(ABC):

    @abstractmethod
    def save(self, meta: ArxivMetadataEntity) -> ArxivMetadataEntity:
        """Persist a new ArxivMetadata row. Returns saved entity with id populated."""

    @abstractmethod
    def find_by_article_id(self, article_id: UUID) -> Optional[ArxivMetadataEntity]:
        """Return ArxivMetadataEntity for this article, or None."""
