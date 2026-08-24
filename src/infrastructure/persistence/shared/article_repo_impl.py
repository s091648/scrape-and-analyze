from typing import Optional, Set
from uuid import UUID, uuid4

from src.infrastructure.persistence.shared.article_mapper import to_article_entity, to_article_model_kwargs
from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArticleRepository(ArticleRepository):
    """SQLAlchemy implementation of the ArticleRepository interface."""

    def __init__(self, session) -> None:
        self._session = session

    def find_by_url_hash(self, url_hash: str) -> Optional[Article]:
        """Look up an article by its URL hash; returns None if not found."""
        from models.article import Article as ArticleModel
        row = self._session.query(ArticleModel).filter_by(url_hash=url_hash).first()
        return to_article_entity(row) if row else None

    def save(self, article: Article) -> Article:
        """Persist a new article and return the entity with DB-generated fields."""
        from models.article import Article as ArticleModel
        row = ArticleModel(
            **to_article_model_kwargs(article),
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
        )
        self._session.add(row)
        self._session.flush()
        logger.info("article_saved", url=article.url, article_id=str(row.id))
        return to_article_entity(row)

    def has_analysis(self, article_id: UUID) -> bool:
        """Return True if the given article already has an associated analysis."""
        from models.analysis import Analysis
        return self._session.query(Analysis).filter_by(article_id=article_id).first() is not None

    def find_analyzed_url_hashes(self, url_hashes: Set[str]) -> Set[str]:
        """Return the subset of url_hashes that already have an associated analysis."""
        if not url_hashes:
            return set()
        from models.article import Article as ArticleModel
        from models.analysis import Analysis
        rows = (
            self._session.query(ArticleModel.url_hash)
            .join(Analysis, Analysis.article_id == ArticleModel.id)
            .filter(ArticleModel.url_hash.in_(url_hashes))
            .all()
        )
        return {row.url_hash for row in rows}