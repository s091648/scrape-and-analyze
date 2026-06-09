"""
Abstract repository interface for Analysis persistence.
"""
from abc import ABC, abstractmethod

from src.modules.intelligence.domain.entities import Analysis


class AnalysisRepository(ABC):
    """Abstract repository interface for Analysis entity persistence."""

    @abstractmethod
    def save(self, analysis: Analysis) -> None:
        """Persist a new analysis. Returns the saved entity (with id populated)."""
