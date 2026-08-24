from abc import ABC, abstractmethod
from typing import Protocol


class RagIngestionService(ABC):
    @abstractmethod
    def ingest(self, article, full_text: str) -> None: ...


class AsyncRagIngestionService(Protocol):
    """024-async-pipeline-refactor: async sibling — new, separate code from
    RagIngestionService/RagSdkIngestionService (untouched, still used by the
    out-of-scope build_rag_backfill_pipeline() via build_rag_ingestion_service())."""

    async def ingest(self, article, full_text: str) -> None: ...
