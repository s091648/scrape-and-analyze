from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from models.article_metrics import ArticleMetrics
from models.article_metric_value import ArticleMetricValue
from src.modules.collection.domain.repositories import ArticleMetricsRepository


class SqlAlchemyArticleMetricsRepository(ArticleMetricsRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

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
