"""
SQLAlchemy implementation of ArticleRepository.

Maps between the pure-domain ArticleEntity and the ORM Article model.
"""
from typing import Optional
from uuid import UUID

from src.domain.entities.article import ArticleEntity
from src.domain.repositories.article_repository import ArticleRepository
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArticleRepository(ArticleRepository):

    def __init__(self, session) -> None:
        self._session = session

    # ── interface ─────────────────────────────────────────────────────────

    def find_by_url_hash(self, url_hash: str) -> Optional[ArticleEntity]:
        from models.article import Article

        row = self._session.query(Article).filter_by(url_hash=url_hash).first()
        if row is None:
            return None
        return self._to_entity(row)

    def save(self, article: ArticleEntity) -> ArticleEntity:
        from models.article import Article

        row = Article(
            url=article.url,
            url_hash=article.url_hash,
            source=article.source,
            title=article.title,
            content=article.content,
            published_at=article.published_at,
            correlation_id=article.correlation_id,
            metadata_=article.metadata or {},
            topic_id=article.topic_id,
        )
        self._session.add(row)
        self._session.flush()  # populate row.id without committing
        logger.info("article_row_saved", url=article.url, article_id=str(row.id))
        return self._to_entity(row)

    def has_analysis(self, article_id: UUID) -> bool:
        from models.analysis import Analysis

        return (
            self._session.query(Analysis)
            .filter_by(article_id=article_id)
            .first()
        ) is not None

    # ── private ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_entity(row) -> ArticleEntity:
        return ArticleEntity(
            id=row.id,
            url=row.url,
            url_hash=row.url_hash,
            source=row.source,
            title=row.title,
            content=row.content,
            published_at=row.published_at,
            scraped_at=row.scraped_at,
            correlation_id=row.correlation_id,
            metadata=row.metadata_ or {},
        )
