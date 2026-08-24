from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
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


class AsyncAnalysesTranslationRepository(Protocol):
    """024-async-pipeline-refactor: async sibling. Covers exists/find_by_*/save
    — what TranslateArticleUseCase actually calls. find_analyses_without_translation
    is only used by the out-of-scope standalone translate CLI job."""

    async def save(self, content: AnalysesContent) -> None:
        ...

    async def find_by_analysis_id_and_language(
        self, analysis_id: UUID, language: str
    ) -> Optional[AnalysesContent]:
        ...

    async def exists(self, analysis_id: UUID, language: str) -> bool:
        ...
