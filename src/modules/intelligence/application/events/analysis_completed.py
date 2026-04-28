from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AnalysisCompletedEvent:
    """Published by AnalyzeArticleUseCase after successful analysis save."""
    analysis_id: UUID
    article_id: UUID
    summary: Optional[str] = None
    pain_points: Optional[str] = None
    insights: Optional[str] = None
    innovations: Optional[str] = None
