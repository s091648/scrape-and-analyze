from typing import Optional, runtime_checkable, Protocol
from uuid import UUID


@runtime_checkable
class FailedEvent(Protocol):
    task_type: str
    article_id: Optional[UUID]
    analysis_id: Optional[UUID]
    article_url: Optional[str]
    exception_type: Optional[str]
    exception_message: Optional[str]
    context: Optional[dict]
    traceback: Optional[str]
