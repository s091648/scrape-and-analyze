from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from models.article_metrics import ArticleMetrics
from models.article_metric_value import ArticleMetricValue
from src.modules.collection.domain.repositories import ArticleMetricsRepository, StaleArticle

# Articles missing (or with a stale) article_metric_values row for any enabled
# metric_key, restricted to articles that actually carry a DOI/arxiv_id (the
# only identifiers current metric providers can look up by) — see
# research.md §9e for the expression indexes this query relies on.
_STALE_ARTICLES_QUERY = text(
    """
    SELECT a.id, a.metadata
    FROM articles a
    WHERE (a.metadata->>'doi' IS NOT NULL OR a.metadata->>'arxiv_id' IS NOT NULL)
      AND EXISTS (
          SELECT 1 FROM unnest(:metric_keys) AS mk(metric_key)
          WHERE NOT EXISTS (
              SELECT 1 FROM article_metric_values amv
              WHERE amv.article_id = a.id
                AND amv.metric_key = mk.metric_key
                AND amv.last_flushed_at >= now() - interval '1 day'
          )
      )
    LIMIT :limit
    """
)


class SqlAlchemyArticleMetricsRepository(ArticleMetricsRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_stale(self, metric_keys: List[str], limit: int) -> List[StaleArticle]:
        rows = self._session.execute(
            _STALE_ARTICLES_QUERY, {"metric_keys": metric_keys, "limit": limit},
        ).fetchall()
        return [StaleArticle(article_id=row.id, metadata=row.metadata or {}) for row in rows]

    def upsert(self, article_id: UUID, metrics: Dict[str, Any]) -> None:
        """Upsert one article_metric_values row per key in `metrics`, and ensure
        an article_metrics row exists (view_count defaults to 0 on first insert)."""
        article_metrics_stmt = (
            insert(ArticleMetrics)
            .values(article_id=article_id, view_count=0)
            .on_conflict_do_nothing(index_elements=["article_id"])
        )
        self._session.execute(article_metrics_stmt)

        now = datetime.now(timezone.utc)
        for metric_key, value in metrics.items():
            stmt = (
                insert(ArticleMetricValue)
                .values(article_id=article_id, metric_key=metric_key, value=value, last_flushed_at=now)
                .on_conflict_do_update(
                    index_elements=["article_id", "metric_key"],
                    set_={"value": value, "last_flushed_at": now},
                )
            )
            self._session.execute(stmt)

        self._session.commit()
