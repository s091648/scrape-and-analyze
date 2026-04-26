from dataclasses import dataclass
from src.shared.domain.entities.article import Article


@dataclass(frozen=True)
class ArticleProcessedEvent:
    article: Article