from abc import ABC, abstractmethod


class RagIngestionService(ABC):
    @abstractmethod
    def ingest(self, article) -> None: ...
