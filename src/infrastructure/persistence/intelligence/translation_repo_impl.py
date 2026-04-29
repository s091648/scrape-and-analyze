from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from src.modules.intelligence.domain.entities import Translation
from src.modules.intelligence.domain.repositories import TranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyTranslationRepository(TranslationRepository):
    """SQLAlchemy implementation of TranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, translation: Translation) -> None:
        """Save or update a translation."""
        from models.translation import Translation as TranslationModel

        # Check if exists
        existing = self._session.query(TranslationModel).filter_by(
            analysis_id=translation.analysis_id,
            language=translation.language,
        ).first()

        if existing:
            # Update existing
            existing.summary = translation.summary
            existing.pain_points = translation.pain_points
            existing.insights = translation.insights
            existing.innovations = translation.innovations
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            model = TranslationModel(
                analysis_id=translation.analysis_id,
                language=translation.language,
                summary=translation.summary,
                pain_points=translation.pain_points,
                insights=translation.insights,
                innovations=translation.innovations,
            )
            self._session.add(model)

        self._session.commit()
        logger.info(
            "translation_persisted",
            analysis_id=str(translation.analysis_id),
            language=translation.language,
        )

    def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[Translation]:
        """Find translation by analysis ID and language."""
        from models.translation import Translation as TranslationModel

        model = self._session.query(TranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).first()

        if model is None:
            return None

        return Translation(
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

    def find_analyses_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """
        Find analyses that don't have translation for the target language.
        Returns list of dicts with analysis data.
        """
        from models.analysis import Analysis as AnalysisModel
        from models.translation import Translation as TranslationModel

        rows = (
            self._session.query(AnalysisModel)
            .filter(AnalysisModel.language == 'en')
            .filter(~AnalysisModel.translations.any(TranslationModel.language == language))
            .order_by(AnalysisModel.analyzed_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "analysis_id": row.id,
                "article_id": row.article_id,
                "summary": row.summary,
                "pain_points": row.pain_points,
                "insights": row.insights,
                "innovations": row.innovations,
            }
            for row in rows
        ]

    def exists(self, analysis_id: UUID, language: str) -> bool:
        """Check if translation exists for analysis and language."""
        from models.translation import Translation as TranslationModel

        count = self._session.query(TranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).count()

        return count > 0
