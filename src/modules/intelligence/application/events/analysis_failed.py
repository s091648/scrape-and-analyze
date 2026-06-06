from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class AnalysisFailedEvent:
    """Published by ArticleProcessedHandler when LLM analysis or persistence fails."""
    article_id: UUID
    article_url: str
    task_type: str = "analyze"
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
