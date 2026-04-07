"""
Domain entity for Analysis — pure dataclass, zero ORM dependency.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class AnalysisEntity:
    article_id: UUID
    correlation_id: UUID
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    summary: Optional[str]
    model_used: str
    input_tokens: int
    output_tokens: int
    # tag_groups carries [{group: str, tags: [str]}] for the persistence layer to handle
    tag_groups: List[Dict[str, Any]] = field(default_factory=list)
    id: Optional[UUID] = None
    analyzed_at: Optional[datetime] = None
