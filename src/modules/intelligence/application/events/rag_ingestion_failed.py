from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class RagIngestionFailedEvent:
    """Published by RagIngestionHandler when RAG ingestion fails for an article."""
    article_id: UUID
    article_url: str
    task_type: str = "rag_ingest"
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    correlation_id: Optional[str] = None
