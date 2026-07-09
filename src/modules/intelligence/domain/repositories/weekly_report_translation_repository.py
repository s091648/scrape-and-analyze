from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.entities.weekly_report_translation import WeeklyReportTranslation


class WeeklyReportTranslationRepository(ABC):
    """Domain interface for WeeklyReport translation persistence."""

    @abstractmethod
    def save(self, translation: WeeklyReportTranslation) -> None:
        """Upsert a translation keyed on (weekly_report_id, language)."""

    @abstractmethod
    def find_by_report_id_and_language(
        self, weekly_report_id: UUID, language: str
    ) -> Optional[WeeklyReportTranslation]:
        """Return translation for a specific report and language, or None."""

    @abstractmethod
    def exists(self, weekly_report_id: UUID, language: str) -> bool:
        """Return True if a translation exists for (weekly_report_id, language)."""
