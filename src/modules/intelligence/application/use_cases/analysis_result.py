from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from src.modules.intelligence.domain.entities import Analysis


@dataclass(frozen=True)
class AnalysisResult:
    """Return value of AnalyzeArticleUseCase — carries outcome without side effects."""
    success: bool
    article_id: UUID
    article_url: str
    analysis: Optional[Analysis] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    topic_display_name: Optional[str] = None
