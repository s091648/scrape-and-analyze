from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class AnalysesTranslationContent:
    """Translated content of an article analysis."""
    summary: Optional[str]
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]


@dataclass
class AnalysesTranslationResult:
    """Result of a translation operation, including content and outcome status."""
    analysis_id: UUID
    language: str
    content: AnalysesTranslationContent
    success: bool
