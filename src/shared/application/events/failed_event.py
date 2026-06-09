from typing import Optional, runtime_checkable, Protocol
from uuid import UUID


@runtime_checkable
class FailedEvent(Protocol):
    """Protocol for events representing a failed pipeline task with error context."""
    task_type: str
    article_id: Optional[UUID]
    analysis_id: Optional[UUID]
    article_url: Optional[str]
    exception_type: Optional[str]
    exception_message: Optional[str]
    context: Optional[dict]
    traceback: Optional[str]
