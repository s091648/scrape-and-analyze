from abc import ABC, abstractmethod

from src.modules.collection.application.events import PipelineCompletedEvent


class BaseNotifier(ABC):
    """Abstract base for pipeline-completion notification senders."""
    @abstractmethod
    def notify(self, event: PipelineCompletedEvent) -> None: ...