from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ArticleSummaryForReport:
    title: str
    summary: Optional[str] = None
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    innovations: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    citation_count: Optional[int] = None
    view_count: int = 0
    published_at: Optional[datetime] = None
