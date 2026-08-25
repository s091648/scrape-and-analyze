"""
Abstract repository interface for Analysis persistence.
"""
from abc import ABC, abstractmethod
from typing import Protocol

from src.modules.intelligence.domain.entities import Analysis


class AnalysisRepository(ABC):
    """Abstract repository interface for Analysis entity persistence."""

    @abstractmethod
    def save(self, analysis: Analysis) -> None:
        """Persist a new analysis. Returns the saved entity (with id populated)."""


class AsyncAnalysisRepository(Protocol):
    """024-async-pipeline-refactor: async sibling — new, separate code from
    the sync AnalysisRepository/SqlAlchemyAnalysisRepository. Covers only
    `save`, matching AnalyzeArticleUseCase's actual usage (find_missing_analyses/
    scan_missing_analyses are zombie-detection queries not on this pipeline's
    per-article path)."""

    async def save(self, analysis: Analysis) -> None:
        ...
