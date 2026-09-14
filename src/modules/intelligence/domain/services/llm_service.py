from abc import ABC, abstractmethod
from typing import Optional, Protocol, Tuple

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


class LLMService(ABC):
    """Domain interface for LLM-based article analysis and translation."""

    @abstractmethod
    def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        """
        Analyze article content using the given prompt.

        prompt is passed at call time (not at construction) so that each
        article can be analyzed with a topic-specific rendered prompt.

        Returns (AnalysisContent, AnalysisMetadata), or None on failure.
        """
        ...

    @abstractmethod
    def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        """
        Translate content using the given prompt.

        Returns translated text string, or None on failure.
        """
        ...


class AsyncLLMService(Protocol):
    """024-async-pipeline-refactor: async sibling of LLMService — mirrors
    AsyncRagIngestionService's pattern (see rag_ingestion_service.py) of a
    Protocol living alongside the sync ABC rather than converting it in
    place, since sync callers (e.g. the weekly-report/release-notes/
    tag-embedding-backfill entrypoints via build_llm_service()) still depend
    on the synchronous contract. Implemented by AsyncResilientLLMService;
    consumed by AnalyzeArticleUseCase and the async translation use cases
    (TranslateArticleUseCase/TranslateTagsUseCase/TranslateArticleBodyUseCase's
    async siblings)."""

    async def analyze(
        self,
        content: str,
        prompt: str,
    ) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        """Analyze article content using the given prompt; None on failure."""
        ...

    async def translate(
        self,
        content: str,
        prompt: str,
    ) -> Optional[str]:
        """Translate content using the given prompt; None on failure."""
        ...
