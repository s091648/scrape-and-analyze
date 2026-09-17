from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class ArticleSaveFailedEvent:
    """Published by ArticleScrapedHandler when persisting a newly scraped article fails."""
    article_url: str
    task_type: str = "scrape_save"
    article_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    context: Optional[dict] = None
    traceback: Optional[str] = None
    correlation_id: Optional[str] = None
