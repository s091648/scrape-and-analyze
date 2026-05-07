from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from src.modules.intelligence.domain.entities import AnalysisTranslation
from src.modules.intelligence.domain.repositories import AnalysisTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAnalysisTranslationRepository(AnalysisTranslationRepository):
    """SQLAlchemy implementation of AnalysisTranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, translation: AnalysisTranslation) -> None:
        """Save or update an analysis translation."""
        from models.analysis_translation import AnalysisTranslation as AnalysisTranslationModel

        # Check if exists
        existing = self._session.query(AnalysisTranslationModel).filter_by(
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
            model = AnalysisTranslationModel(
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
            "analysis_translation_persisted",
            analysis_id=str(translation.analysis_id),
            language=translation.language,
        )

    def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysisTranslation]:
        """Find analysis translation by analysis ID and language."""
        from models.analysis_translation import AnalysisTranslation as AnalysisTranslationModel

        model = self._session.query(AnalysisTranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).first()

        if model is None:
            return None

        return AnalysisTranslation(
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
        Returns list of dicts with analysis data (content from English translation).
        """
        from models.analysis import Analysis as AnalysisModel
        from models.analysis_translation import AnalysisTranslation as AnalysisTranslationModel

        rows = (
            self._session.query(AnalysisModel)
            .filter(~AnalysisModel.analysis_translations.any(
                AnalysisTranslationModel.language == language
            ))
            .options(joinedload(AnalysisModel.analysis_translations))
            .order_by(AnalysisModel.analyzed_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "analysis_id": row.id,
                "article_id": row.article_id,
                **_extract_en_content(row),
            }
            for row in rows
        ]

    def exists(self, analysis_id: UUID, language: str) -> bool:
        """Check if translation exists for analysis and language."""
        from models.analysis_translation import AnalysisTranslation as AnalysisTranslationModel

        count = self._session.query(AnalysisTranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).count()

        return count > 0


def _extract_en_content(analysis_row) -> dict:
    """Extract English content from an analysis row's analysis_translations relationship."""
    en_trans = next(
        (t for t in analysis_row.analysis_translations if t.language == 'en'),
        None,
    )
    return {
        "summary": en_trans.summary if en_trans else None,
        "pain_points": en_trans.pain_points if en_trans else None,
        "insights": en_trans.insights if en_trans else None,
        "innovations": en_trans.innovations if en_trans else None,
    }
