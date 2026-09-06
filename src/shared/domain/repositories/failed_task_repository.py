from abc import ABC, abstractmethod
from typing import Protocol, Sequence

from src.modules.collection.domain.entities import FailedTask


class FailedTaskRepository(ABC):
    """Abstract repository interface for persisting FailedTask records."""

    @abstractmethod
    def save(self, task: FailedTask) -> None:
        """Persist a new FailedTask record."""


class AsyncFailedTaskRepository(Protocol):
    """024-async-pipeline-refactor: async sibling — new, separate code from
    the sync FailedTaskRepository/SqlAlchemyFailedTaskRepository."""

    async def save(self, task: FailedTask) -> None:
        ...

    async def save_many(self, tasks: Sequence[FailedTask]) -> None:
        """Persist several FailedTask records in one transaction — for
        run-end bulk recording (e.g. every article skipped after the RAG
        daily-quota circuit breaker tripped), instead of one commit each."""
        ...
