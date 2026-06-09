"""
Domain entity for FailedTask — pure dataclass, zero ORM dependency.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class FailedTask:
    """Records a pipeline failure (scrape, analyze, or translate) for later inspection and retry."""
    task_type: str
    id: UUID = field(default_factory=uuid4)
    article_url: Optional[str] = None
    article_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    failed_at: Optional[datetime] = None
    resolved: bool = False
