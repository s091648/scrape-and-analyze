from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class TranslationFailedEvent:
    """Published when article or tag translation fails."""
    analysis_id: UUID
    article_id: UUID
    task_type: str = "translate_article"
    article_url: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    correlation_id: Optional[str] = None
