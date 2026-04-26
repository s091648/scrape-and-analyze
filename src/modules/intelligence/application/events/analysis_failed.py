from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AnalysisFailedEvent:
    """Published by AnalyzeArticleUseCase when LLM analysis or persistence fails."""
    article_id: UUID
    article_url: str
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
