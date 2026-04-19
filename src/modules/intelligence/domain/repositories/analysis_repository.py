"""
Abstract repository interface for Analysis persistence.
"""
from abc import ABC, abstractmethod

from src.modules.intelligence.domain import Analysis


class AnalysisRepository(ABC):

    @abstractmethod
    def save(self, analysis: Analysis) -> None:
        """Persist a new analysis. Returns the saved entity (with id populated)."""
