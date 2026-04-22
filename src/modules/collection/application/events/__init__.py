# Legacy re-export for backward compatibility during migration
# Use ScrapedArticleDTO from application.dtos instead
from src.modules.collection.application.dtos import ScrapedArticleDTO as ArticleScrapedEvent


__all__ = [
    'ArticleScrapedEvent',  # Deprecated: use ScrapedArticleDTO from application.dtos
]