from dataclasses import dataclass, field
from datetime import datetime

from src.modules.collection.domain.value_objects import ScrapedArticle


@dataclass(frozen=True)
class ArticleCollectedEvent:
    """
    Domain event - collection bounded context 內部的事件。

    在 CollectionPipeline 完成 Phase 2 (fetch) 後發布，
    表示一篇文章已成功收集。

    這個事件只在 collection context 內部使用，
    跨 context 的整合事件應放在 application/events/。
    """
    article: ScrapedArticle
    collected_at: datetime = field(default_factory=datetime.utcnow)