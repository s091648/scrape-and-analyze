from abc import ABC, abstractmethod
from typing import Any, Dict
from uuid import UUID


class ArticleMetricsRepository(ABC):
    @abstractmethod
    def upsert(self, article_id: UUID, metrics: Dict[str, Any]) -> None:
        """Upsert one article_metric_values row per (article_id, metric_key) in `metrics`."""
