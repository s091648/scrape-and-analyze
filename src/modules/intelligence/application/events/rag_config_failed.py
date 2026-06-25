from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class RagConfigFailedEvent:
    """Published at startup when VECTOR_DB_* vars are set but RAG is still misconfigured.
    article_id/url are None since this is not per-article."""
    task_type: str = "rag_config"
    article_id: Optional[UUID] = None
    article_url: Optional[str] = None
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    correlation_id: Optional[str] = None
