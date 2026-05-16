from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from src.modules.intelligence.domain.entities import AnalysesContent
from src.modules.intelligence.domain.repositories import AnalysesTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyAnalysesTranslationRepository(AnalysesTranslationRepository):
    """SQLAlchemy implementation of AnalysesTranslationRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, content: AnalysesContent) -> None:
        """Save or update an analysis content."""
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        # Check if exists
        existing = self._session.query(AnalysesTranslationModel).filter_by(
            analysis_id=content.analysis_id,
            language=content.language,
        ).first()

        if existing:
            # Update existing
            existing.summary = content.summary
            existing.pain_points = content.pain_points
            existing.insights = content.insights
            existing.innovations = content.innovations
            existing.updated_at = datetime.utcnow()
        else:
            # Create new
            model = AnalysesTranslationModel(
                analysis_id=content.analysis_id,
                language=content.language,
                summary=content.summary,
                pain_points=content.pain_points,
                insights=content.insights,
                innovations=content.innovations,
            )
            self._session.add(model)

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info(
            "analyses_translation_persisted",
            analysis_id=str(content.analysis_id),
            language=content.language,
        )

    def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysesContent]:
        """Find analysis translation by analysis ID and language."""
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        model = self._session.query(AnalysesTranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).first()

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

    def find_analyses_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """
        Find analyses that don't have translation for the target language.
        Returns list of dicts with analysis data (content from English translation).
        """
        from models.analysis import Analysis as AnalysisModel
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        rows = (
            self._session.query(AnalysisModel)
            .filter(~AnalysisModel.analyses_translation.any(
                AnalysesTranslationModel.language == language
            ))
            .options(joinedload(AnalysisModel.analyses_translation))
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
        from models.analyses_translation import AnalysesTranslation as AnalysesTranslationModel

        count = self._session.query(AnalysesTranslationModel).filter_by(
            analysis_id=analysis_id,
            language=language,
        ).count()

        return count > 0

def _extract_en_content(analysis_row) -> dict:
    """Extract English content from an analysis row's analyses_translation relationship."""
    en_trans = next(
        (t for t in analysis_row.analyses_translation if t.language == 'en'),
        None,
    )
    return {
        "summary": en_trans.summary if en_trans else None,
        "pain_points": en_trans.pain_points if en_trans else None,
        "insights": en_trans.insights if en_trans else None,
        "innovations": en_trans.innovations if en_trans else None,
    }
