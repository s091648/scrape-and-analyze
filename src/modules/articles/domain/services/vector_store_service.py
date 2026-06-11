from abc import ABC, abstractmethod


class VectorStoreService(ABC):
    @abstractmethod
    def ingest(self, article) -> None: ...
