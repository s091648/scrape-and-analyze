from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from uuid import UUID

from src.modules.intelligence.domain.entities import AnalysisTranslation


class AnalysisTranslationRepository(ABC):
    """Domain interface for analysis translation persistence."""

    @abstractmethod
    def save(self, translation: AnalysisTranslation) -> None:
        """Save or update an analysis translation."""
        ...

    @abstractmethod
    def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysisTranslation]:
        """Find analysis translation by analysis ID and language."""
        ...

    @abstractmethod
    def find_analyses_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """
        Find analyses that don't have translation for the target language.
        Returns list of dicts with analysis data (content read from English translation).
        """
        ...

    @abstractmethod
    def exists(self, analysis_id: UUID, language: str) -> bool:
        """Check if translation exists for analysis and language."""
        ...


class TagTranslationRepository(ABC):
    """Domain interface for tag translation persistence."""

    @abstractmethod
    def save_tag_translation(self, tag_id: UUID, language: str, name: str) -> None:
        """Save or update a tag translation."""
        ...

    @abstractmethod
    def find_tags_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Find tags that don't have translation for the target language."""
        ...

    @abstractmethod
    def save_group_translation(
        self, tag_group_definition_id: UUID, language: str, display_name: str
    ) -> None:
        """Save or update a tag group display_name translation."""
        ...

    @abstractmethod
    def find_groups_without_translation(
        self, language: str, limit: int
    ) -> List[dict]:
        """Find tag group definitions without translation for the target language."""
        ...
