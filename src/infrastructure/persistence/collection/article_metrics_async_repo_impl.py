from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.article_metrics import ArticleMetrics
from models.article_metric_value import ArticleMetricValue
from src.modules.collection.domain.repositories import AsyncArticleMetricsRepository


class AsyncSqlAlchemyArticleMetricsRepository(AsyncArticleMetricsRepository):
    """024-async-pipeline-refactor: async sibling of
    SqlAlchemyArticleMetricsRepository (untouched — find_stale, used only by
    the out-of-scope refresh-metrics job, is not mirrored). Added after
    discovering ProcessScrapedArticleUseCase calls `upsert` per-article in
    the now-concurrent downstream path — planning had missed this."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, article_id: UUID, metrics: Dict[str, Any]) -> None:
        """Upsert one article_metric_values row per key in `metrics`, and ensure
        an article_metrics row exists (view_count defaults to 0 on first insert)."""
        article_metrics_stmt = (
            insert(ArticleMetrics)
            .values(article_id=article_id, view_count=0)
            .on_conflict_do_nothing(index_elements=["article_id"])
        )
        await self._session.execute(article_metrics_stmt)

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
            await self._session.execute(stmt)

        await self._session.commit()
