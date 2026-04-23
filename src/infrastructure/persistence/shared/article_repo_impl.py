from typing import Optional
from uuid import UUID, uuid4

from src.shared.domain.entities import Article
from src.shared.domain.repositories import ArticleRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArticleRepository(ArticleRepository):

    def __init__(self, session) -> None:
        self._session = session

    def find_by_url_hash(self, url_hash: str) -> Optional[Article]:
        from models.article import Article as ArticleModel
        row = self._session.query(ArticleModel).filter_by(url_hash=url_hash).first()
        return self._to_entity(row) if row else None

    def save(self, article: Article) -> Article:
        from models.article import Article as ArticleModel
        row = ArticleModel(
            id=article.id,
            url=article.url,
            url_hash=article.url_hash,
            source=article.source,
            title=article.title,
            content=article.content,
            published_at=article.published_at,
            metadata_=article.metadata or {},
            topic_id=article.topic_id,
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
        )
        self._session.add(row)
        self._session.flush()
        logger.info("article_saved", url=article.url, article_id=str(row.id))
        return self._to_entity(row)

    def has_analysis(self, article_id: UUID) -> bool:
        from models.analysis import Analysis
        return self._session.query(Analysis).filter_by(article_id=article_id).first() is not None

    @staticmethod
    def _to_entity(row) -> Article:
        return Article(
            id=row.id,
            url=row.url,
            url_hash=row.url_hash,
            source=row.source,
            title=row.title,
            content=row.content,
            published_at=row.published_at,
            scraped_at=row.scraped_at,
            metadata=row.metadata_ or {},
            topic_id=row.topic_id,
        )