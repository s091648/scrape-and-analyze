from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.entities import Analysis


@dataclass(frozen=True)
class AnalysisResult:
    """Return value of AnalyzeArticleUseCase.execute() on success — a failure raises instead."""
    article_id: UUID
    article_url: str
    analysis: Analysis
    topic_display_name: Optional[str] = None
