from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.modules.collection.domain.value_objects import ScrapedArticle


@dataclass
class ScrapedArticleDTO:
    """
    Application DTO - 從 scraper fetch() 回傳的 data carrier。

    這是跨 layer 傳遞的資料物件，不是 domain object。
    在 infrastructure → application 的邊界使用。

    與 ScrapedArticle (domain value object) 的區別：
    - ScrapedArticle: immutable, 代表領域概念
    - ScrapedArticleDTO: mutable, 用於資料傳遞和序列化
    """
    url: str
    title: str
    content: str
    source: str
    topic_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    authors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_scraped_article(cls, article: ScrapedArticle) -> "ScrapedArticleDTO":
        """從 domain ScrapedArticle 轉換為 DTO"""
        return cls(
            url=article.url,
            title=article.title,
            content=article.content,
            source=article.source,
            topic_id=article.topic_id,
            published_at=article.published_at,
            authors=article.authors,
            metadata=article.extra,
        )

    def to_scraped_article(self) -> ScrapedArticle:
        """從 DTO 轉換為 domain ScrapedArticle"""
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