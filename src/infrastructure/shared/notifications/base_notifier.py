from abc import ABC, abstractmethod

from src.modules.collection.application.events import PipelineCompletedEvent


class BaseNotifier(ABC):
    @abstractmethod
    def notify(self, event: PipelineCompletedEvent) -> None: ...