from abc import ABC, abstractmethod
from typing import Optional, Tuple

from src.modules.intelligence.domain.value_objects import AnalysisContent, AnalysisMetadata


class LLMService(ABC):
    """Domain interface for LLM-based article analysis."""

    @abstractmethod
    def analyze(self, content: str) -> Optional[Tuple[AnalysisContent, AnalysisMetadata]]:
        """
        Analyze article content and return (AnalysisContent, AnalysisMetadata).
        Returns None if the LLM call fails or returns an invalid response.
        """
        ...
