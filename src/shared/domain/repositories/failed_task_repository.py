from abc import ABC, abstractmethod

from src.modules.collection.domain.entities import FailedTask


class FailedTaskRepository(ABC):

    @abstractmethod
    def save(self, task: FailedTask) -> None:
        """Persist a new FailedTask record."""
