from abc import ABC, abstractmethod
from typing import List

from src.scrapers.scrapers.article import ScrapedArticle  # re-exported for back-compat

__all__ = ['BaseScraper', 'ScrapedArticle']


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def scrape(self) -> List[ScrapedArticle]:
        """Legacy interface. Replaced by discover() in a later task."""
        pass
