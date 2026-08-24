from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.intelligence.domain.entities import Analysis
from src.modules.intelligence.domain.repositories import AsyncAnalysisRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class AsyncSqlAlchemyAnalysisRepository(AsyncAnalysisRepository):
    """024-async-pipeline-refactor: async sibling of SqlAlchemyAnalysisRepository
    (untouched). Covers only `save` — see AsyncAnalysisRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, analysis: Analysis) -> None:
        """Persist an Analysis entity and its English translation row, then commit."""
        from models.analysis import Analysis as AnalysisModel
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        content = analysis.analysis_content
        metadata = analysis.analysis_metadata

        row = AnalysisModel(
            article_id=analysis.article_id,
            correlation_id=uuid4(),  # legacy NOT NULL column; no longer in domain model
            model_used=metadata.model_used,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
        )
        self._session.add(row)
        await self._session.flush()

        # Backfill the DB-generated id into the domain entity
        analysis.id = row.id

        # Create English translation row with content
        translation_row = AnalysesTranslationModel(
            analysis_id=row.id,
            language='en',
            summary=content.summary,
            pain_points=content.pain_points,
            insights=content.insights,
            innovations=content.innovations,
        )
        self._session.add(translation_row)

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        logger.info("analysis_saved", article_id=str(analysis.article_id), model=metadata.model_used)
