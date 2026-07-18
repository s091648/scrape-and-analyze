from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID


@dataclass(frozen=True)
class ArticleSummaryForReport:
    article_id: UUID
    title: str
    summary: Optional[str] = None
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    innovations: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    # Deployment-defined catalog metrics for this article (metric_key -> value), sourced from
    # article_metric_values. Not hardcoded to citation_count — a deployment may track any set of
    # metrics (citation_count, impact_factor, h_index, ...) or none at all. Only present keys
    # (non-NULL values) are included.
    metrics: Dict[str, float] = field(default_factory=dict)
    view_count: int = 0
    published_at: Optional[datetime] = None
