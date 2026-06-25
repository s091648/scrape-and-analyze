from dataclasses import dataclass
from src.shared.domain.entities.article import Article


@dataclass(frozen=True)
class ArticleProcessedEvent:
    """Event emitted after an article has been successfully processed and persisted."""
    article: Article
    full_text: str = ""