from abc import ABC, abstractmethod
from typing import Protocol


class RagIngestionService(ABC):
    @abstractmethod
    def ingest(self, article, full_text: str) -> None: ...


class AsyncRagIngestionService(Protocol):
    """024-async-pipeline-refactor: async sibling — new, separate code from
    RagIngestionService/RagSdkIngestionService (untouched, still used by
    build_rag_ingestion_service()). As of User Story 6, build_rag_backfill_pipeline()
    also uses this (via build_async_rag_ingestion_service()), not the sync original —
    see research.md item 11."""

    async def ingest(self, article, full_text: str) -> None: ...

    async def aclose(self) -> None:
        """Release background resources (the RAG SDK's EmbeddingBatchCoordinator
        worker task) — called once per run, after every ingest() call has
        settled (research.md item 11)."""
        ...
