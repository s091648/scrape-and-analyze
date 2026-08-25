from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.persistence.shared.article_mapper import to_article_entity, to_article_model_kwargs
from src.shared.domain.entities import Article
from src.shared.domain.repositories import AsyncArticleRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyArticleRepository(AsyncArticleRepository):
    """024-async-pipeline-refactor: async sibling of SqlAlchemyArticleRepository
    (untouched). Constructed fresh per per-article asyncio.Task, holding that
    task's own AsyncSession — never shared across concurrently-running tasks.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_url_hash(self, url_hash: str) -> Optional[Article]:
        """Look up an article by its URL hash; returns None if not found."""
        from models.article import Article as ArticleModel
        result = await self._session.execute(
            select(ArticleModel).filter_by(url_hash=url_hash)
        )
        row = result.scalars().first()
        return to_article_entity(row) if row else None

    async def save(self, article: Article) -> Article:
        """Persist a new article and return the entity with DB-generated fields."""
        from models.article import Article as ArticleModel
        row = ArticleModel(
            **to_article_model_kwargs(article),
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
        )
        self._session.add(row)
        await self._session.flush()
        logger.info("article_saved", url=article.url, article_id=str(row.id))
        return to_article_entity(row)

    async def has_analysis(self, article_id) -> bool:
        """Return True if the given article already has an associated analysis."""
        from models.analysis import Analysis
        result = await self._session.execute(
            select(Analysis.id).filter_by(article_id=article_id)
        )
        return result.scalars().first() is not None
