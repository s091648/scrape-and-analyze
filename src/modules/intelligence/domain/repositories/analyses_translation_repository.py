from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID

from src.modules.intelligence.domain.entities import AnalysesContent


class AnalysesTranslationRepository(ABC):
    """Domain interface for analysis content persistence."""

    @abstractmethod
    def save(self, content: AnalysesContent) -> None:
        """Save or update analysis content."""
        ...

    @abstractmethod
    def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysesContent]:
        """Find analysis content by analysis ID and language."""
        ...

    @abstractmethod
    def find_analyses_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """
        Find analyses that don't have content for the target language.
        Returns list of dicts with analysis data (content read from English entry).
        """
        ...

    @abstractmethod
    def exists(self, analysis_id: UUID, language: str) -> bool:
        """Check if content exists for analysis and language."""
        ...

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current persistence transaction."""
        ...
