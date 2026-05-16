from abc import ABC, abstractmethod
from typing import Optional, Tuple

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
