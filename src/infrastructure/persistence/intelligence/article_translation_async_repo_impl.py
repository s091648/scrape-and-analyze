from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.intelligence.domain.repositories import AsyncArticleTranslationRepository
from src.modules.intelligence.domain.value_objects.analyses_translation_content import ArticleBodyTranslationContent
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyArticleTranslationRepository(AsyncArticleTranslationRepository):
    """024-async-pipeline-refactor: async sibling of
    SqlAlchemyArticleTranslationRepository (untouched)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, article_id: UUID, language: str, title: str, content: Optional[str]) -> None:
        """The whole body — including the initial lookup SELECT, not just commit()
        — is one rollback-and-reraise guard: this session is shared with
        FailedTaskPersistenceHandler (bootstrap.py's translation_downstream_builder),
        so a failure left un-rolled-back would leave the session unusable for that
        handler's own later commit(), silently losing the failure record
        (CodeRabbit review, 026-rate-limit-codegen PR #127)."""
        from models.article_translation import ArticleTranslation

        try:
            result = await self._session.execute(
                select(ArticleTranslation).filter_by(article_id=article_id, language=language)
            )
            existing = result.scalars().first()

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

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        logger.info("article_translation_persisted", article_id=str(article_id), language=language)

    async def find_by_article_id_and_language(
        self, article_id: UUID, language: str
    ) -> Optional[ArticleBodyTranslationContent]:
        from models.article_translation import ArticleTranslation

        result = await self._session.execute(
            select(ArticleTranslation).filter_by(article_id=article_id, language=language)
        )
        row = result.scalars().first()

        if row is None:
            return None

        return ArticleBodyTranslationContent(title=row.title, content=row.content)

    async def exists(self, article_id: UUID, language: str) -> bool:
        from models.article_translation import ArticleTranslation

        result = await self._session.execute(
            select(ArticleTranslation.id).filter_by(article_id=article_id, language=language)
        )
        return result.scalars().first() is not None
