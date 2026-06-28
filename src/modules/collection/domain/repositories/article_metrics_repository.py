from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


class ArticleMetricsRepository(ABC):
    @abstractmethod
    def upsert(self, article_id: UUID, citation_count: Optional[int]) -> None:
        """Upsert article_metrics row with citation_count; view_count defaults to 0."""
