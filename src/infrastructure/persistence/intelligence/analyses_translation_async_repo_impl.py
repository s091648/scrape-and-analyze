from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.intelligence.domain.entities import AnalysesContent
from src.modules.intelligence.domain.repositories import AsyncAnalysesTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyAnalysesTranslationRepository(AsyncAnalysesTranslationRepository):
    """024-async-pipeline-refactor: async sibling of
    SqlAlchemyAnalysesTranslationRepository (untouched)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, content: AnalysesContent) -> None:
        """Save or update an analysis content.

        The whole body — including the initial lookup SELECT, not just commit()
        — is one rollback-and-reraise guard: this session is shared with
        FailedTaskPersistenceHandler (bootstrap.py's translation_downstream_builder),
        so a failure left un-rolled-back would leave the session unusable for that
        handler's own later commit(), silently losing the failure record
        (CodeRabbit review, 026-rate-limit-codegen PR #127)."""
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        try:
            result = await self._session.execute(
                select(AnalysesTranslationModel).filter_by(
                    analysis_id=content.analysis_id,
                    language=content.language,
                )
            )
            existing = result.scalars().first()

            if existing:
                existing.summary = content.summary
                existing.pain_points = content.pain_points
                existing.insights = content.insights
                existing.innovations = content.innovations
                existing.updated_at = datetime.utcnow()
            else:
                model = AnalysesTranslationModel(
                    analysis_id=content.analysis_id,
                    language=content.language,
                    summary=content.summary,
                    pain_points=content.pain_points,
                    insights=content.insights,
                    innovations=content.innovations,
                )
                self._session.add(model)

            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        logger.info(
            "analyses_translation_persisted",
            analysis_id=str(content.analysis_id),
            language=content.language,
        )

    async def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysesContent]:
        """Find analysis translation by analysis ID and language."""
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        result = await self._session.execute(
            select(AnalysesTranslationModel).filter_by(
                analysis_id=analysis_id,
                language=language,
            )
        )
        model = result.scalars().first()

        if model is None:
            return None

        return AnalysesContent(
            id=model.id,
            analysis_id=model.analysis_id,
            language=model.language,
            summary=model.summary,
            pain_points=model.pain_points,
            insights=model.insights,
            innovations=model.innovations,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def exists(self, analysis_id: UUID, language: str) -> bool:
        """Check if translation exists for analysis and language."""
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        result = await self._session.execute(
            select(AnalysesTranslationModel.id).filter_by(
                analysis_id=analysis_id,
                language=language,
            )
        )
        return result.scalars().first() is not None

    async def rollback(self) -> None:
        """Roll back the current transaction — used by AnalysisCompletedHandler
        when find_by_analysis_id_and_language() itself raises, so this shared
        per-article-downstream session stays usable for whatever runs next on it
        (mirrors AsyncTagRepository.rollback())."""
        await self._session.rollback()
