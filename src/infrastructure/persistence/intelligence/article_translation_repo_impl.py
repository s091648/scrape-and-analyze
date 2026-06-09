from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.modules.intelligence.domain.repositories.article_translation_repository import ArticleTranslationRepository
from src.modules.intelligence.domain.value_objects.analyses_translation_content import ArticleBodyTranslationContent
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyArticleTranslationRepository(ArticleTranslationRepository):
    """SQLAlchemy implementation of ArticleTranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, article_id: UUID, language: str, title: str, content: Optional[str]) -> None:
        from models.article_translation import ArticleTranslation

        existing = self._session.query(ArticleTranslation).filter_by(
            article_id=article_id,
            language=language,
        ).first()

        if existing:
            existing.title = title
            existing.content = content
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self._session.add(ArticleTranslation(
                article_id=article_id,
                language=language,
                title=title,
                content=content,
            ))

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        logger.info("article_translation_persisted", article_id=str(article_id), language=language)

    def find_by_article_id_and_language(
        self, article_id: UUID, language: str
    ) -> Optional[ArticleBodyTranslationContent]:
        from models.article_translation import ArticleTranslation

        row = self._session.query(ArticleTranslation).filter_by(
            article_id=article_id,
            language=language,
        ).first()

        if row is None:
            return None

        return ArticleBodyTranslationContent(title=row.title, content=row.content)

    def exists(self, article_id: UUID, language: str) -> bool:
        from models.article_translation import ArticleTranslation

        return self._session.query(ArticleTranslation).filter_by(
            article_id=article_id,
            language=language,
        ).count() > 0

    def find_articles_without_translation(self, language: str, limit: int) -> List[dict]:
        from models.article import Article
        from models.article_translation import ArticleTranslation

        rows = (
            self._session.query(Article)
            .filter(~Article.article_translations.any(
                ArticleTranslation.language == language
            ))
            .order_by(Article.scraped_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "article_id": row.id,
                "title": row.title,
                "content": row.content,
            }
            for row in rows
        ]
