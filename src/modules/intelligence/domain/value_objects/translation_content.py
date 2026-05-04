from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass
class TranslationContent:
    """Translated content of an article analysis."""
    summary: Optional[str]
    pain_points: Optional[str]
    insights: Optional[str]
    innovations: Optional[str]


@dataclass
class TranslationResult:
    """Result of a translation operation, including content and outcome status."""
    analysis_id: UUID
    language: str
    content: TranslationContent
    success: bool
