from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass(frozen=True)
class ScrapedArticle:
    """
    Domain value object - 統一的 scraper fetch() 回傳類型。

    代表從 source 抓取下來的文章內容，是 collection bounded context
    內部的 domain object，用於 Phase 1 → Phase 2 的資料傳遞。
    """
    url: str
    title: str
    content: str
    source: str
    topic_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    authors: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    full_text: str = ""