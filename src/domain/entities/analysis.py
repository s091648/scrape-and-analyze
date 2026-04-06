"""
Domain entity for Analysis — pure dataclass, zero ORM dependency.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class AnalysisEntity:
    article_id: UUID
    correlation_id: UUID
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    model_used: str
    input_tokens: int
    output_tokens: int
    id: Optional[UUID] = None
    analyzed_at: Optional[datetime] = None
