from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Translation:
    """Domain entity representing a translated analysis."""
    id: UUID
    analysis_id: UUID
    language: str
    summary: Optional[str]
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]
    created_at: datetime
    updated_at: datetime

    def __init__(
        self,
        analysis_id: UUID,
        language: str,
        summary: Optional[str] = None,
        pain_points: Optional[str] = None,
        insights: Optional[str] = None,
        innovations: Optional[str] = None,
        id: Optional[UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.analysis_id = analysis_id
        self.language = language
        self.summary = summary
        self.pain_points = pain_points
        self.insights = insights
        self.innovations = innovations
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
