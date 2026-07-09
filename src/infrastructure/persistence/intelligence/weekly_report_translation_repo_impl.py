from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.modules.intelligence.domain.entities.weekly_report_translation import WeeklyReportTranslation
from src.modules.intelligence.domain.repositories.weekly_report_translation_repository import WeeklyReportTranslationRepository
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SqlAlchemyWeeklyReportTranslationRepository(WeeklyReportTranslationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, translation: WeeklyReportTranslation) -> None:
        from models.weekly_report_translation import WeeklyReportTranslation as WeeklyReportTranslationModel

        existing = (
            self._session.query(WeeklyReportTranslationModel)
            .filter_by(
                weekly_report_id=translation.weekly_report_id,
                language=translation.language,
            )
            .first()
        )

        if existing:
            existing.title = translation.title
            existing.summary_text = translation.summary_text
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self._session.add(WeeklyReportTranslationModel(
                weekly_report_id=translation.weekly_report_id,
                language=translation.language,
                title=translation.title,
                summary_text=translation.summary_text,
            ))

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        logger.info(
            "weekly_report_translation_persisted",
            report_id=str(translation.weekly_report_id),
            language=translation.language,
        )

    def find_by_report_id_and_language(
        self, weekly_report_id: UUID, language: str
    ) -> Optional[WeeklyReportTranslation]:
        from models.weekly_report_translation import WeeklyReportTranslation as WeeklyReportTranslationModel

        row = (
            self._session.query(WeeklyReportTranslationModel)
            .filter_by(weekly_report_id=weekly_report_id, language=language)
            .first()
        )
        if row is None:
            return None
        return WeeklyReportTranslation(
            id=row.id,
            weekly_report_id=row.weekly_report_id,
            language=row.language,
            title=row.title,
            summary_text=row.summary_text,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def exists(self, weekly_report_id: UUID, language: str) -> bool:
        from models.weekly_report_translation import WeeklyReportTranslation as WeeklyReportTranslationModel

        return (
            self._session.query(WeeklyReportTranslationModel)
            .filter_by(weekly_report_id=weekly_report_id, language=language)
            .count()
        ) > 0
