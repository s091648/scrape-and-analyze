from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.modules.collection.domain.value_objects import ScrapedArticle


@dataclass(frozen=True)
class ArticleScrapedEvent:
    """
    Application event — 文章抓取完成後發布的事件。

    在 infrastructure → application 邊界使用，由 event bus 廣播給 handler。
    與 ScrapedArticle (domain value object) 的區別：
    - ScrapedArticle: immutable domain value object
    - ArticleScrapedEvent: immutable application event
    """
    url: str
    title: str
    content: str
    source: str
    topic_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    authors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    full_text: str = ""

    @classmethod
    def from_scraped_article(cls, article: ScrapedArticle) -> "ArticleScrapedEvent":
        """從 domain ScrapedArticle 轉換為 event"""
        return cls(
            url=article.url,
            title=article.title,
            content=article.content,
            source=article.source,
            topic_id=article.topic_id,
            published_at=article.published_at,
            authors=article.authors,
            metadata=article.extra,
            full_text=article.full_text,
        )

    def to_scraped_article(self) -> ScrapedArticle:
        """從 event 轉換為 domain ScrapedArticle"""
        return ScrapedArticle(
            url=self.url,
            title=self.title,
            content=self.content,
            source=self.source,
            topic_id=self.topic_id,
            published_at=self.published_at,
            authors=self.authors,
            extra=self.metadata,
        )
