from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Protocol
from uuid import UUID


@dataclass(frozen=True)
class StaleArticle:
    """One article whose value for at least one tracked metric_key is missing
    or hasn't been refreshed in over a day."""
    article_id: UUID
    metadata: Dict[str, Any]


class ArticleMetricsRepository(ABC):
    @abstractmethod
    def find_stale(self, metric_keys: List[str], limit: int) -> List[StaleArticle]:
        """Articles carrying a DOI/arxiv_id (the only identifiers current metric
        providers can look up by) that are missing, or have a stale (>1 day),
        article_metric_values row for any of `metric_keys`."""

    @abstractmethod
    def upsert(self, article_id: UUID, metrics: Dict[str, Any]) -> None:
        """Upsert one article_metric_values row per (article_id, metric_key) in `metrics`."""


class AsyncArticleMetricsRepository(Protocol):
    """024-async-pipeline-refactor: async sibling covering only `upsert` —
    the method ProcessScrapedArticleUseCase actually calls per-article in the
    now-concurrent downstream path. `find_stale` is only used by the
    out-of-scope refresh-metrics job and is deliberately not mirrored here.
    Discovered during implementation (planning had mis-scoped this repository
    as upstream-only — it is not; corrected here rather than left wrong)."""

    async def upsert(self, article_id: UUID, metrics: Dict[str, Any]) -> None:
        ...
