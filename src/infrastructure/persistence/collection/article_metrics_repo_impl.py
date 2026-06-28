from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from models.article_metrics import ArticleMetrics
from src.modules.collection.domain.repositories import ArticleMetricsRepository


class SqlAlchemyArticleMetricsRepository(ArticleMetricsRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, article_id: UUID, citation_count: Optional[int]) -> None:
        stmt = (
            insert(ArticleMetrics)
            .values(article_id=article_id, citation_count=citation_count, view_count=0)
            .on_conflict_do_update(
                index_elements=["article_id"],
                set_={"citation_count": citation_count},
            )
        )
        self._session.execute(stmt)
        self._session.commit()
