from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass(frozen=True)
class ArticleScrapedEvent:
    """Internal collection event — published by infrastructure scrapers after a successful fetch."""
    url: str
    title: str
    content: str
    source: str
    topic_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
