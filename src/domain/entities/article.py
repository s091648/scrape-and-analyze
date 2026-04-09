"""
Domain entity for Article — pure dataclass, zero ORM dependency.

The SQLAlchemy model lives in models/article.py (unchanged).
This entity is used by application-layer use cases to avoid coupling
business logic to the ORM.  The infrastructure persistence layer
(Phase 7) is responsible for mapping between the two.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass
class ArticleEntity:
    url: str
    url_hash: str
    source: str
    title: str
    content: str
    correlation_id: UUID
    id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    topic_id: Optional[UUID] = None
