"""
Domain entity for FailedTask — pure dataclass, zero ORM dependency.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class FailedTaskEntity:
    task_type: str
    id: Optional[UUID] = None
    article_url: Optional[str] = None
    article_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    failed_at: Optional[datetime] = None
    resolved: bool = False
