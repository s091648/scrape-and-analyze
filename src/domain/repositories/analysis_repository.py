"""
Abstract repository interface for Analysis persistence.
"""
from abc import ABC, abstractmethod

from src.domain.entities.analysis import AnalysisEntity


class AnalysisRepository(ABC):

    @abstractmethod
    def save(self, analysis: AnalysisEntity) -> AnalysisEntity:
        """Persist a new analysis. Returns the saved entity (with id populated)."""
