from abc import ABC, abstractmethod
from typing import List

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.strategy.scrape_task import ScrapeTask

__all__ = ['BaseScraper', 'ScrapedArticle']


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def discover(self) -> List[ScrapeTask]:
        """
        Phase 1: enumerate all work items for this source.
        Makes the minimum HTTP requests needed to find article URLs
        (e.g. one feed fetch, one listing page fetch).
        Returns [] on any failure.
        """
        pass

    def scrape(self) -> List[ScrapedArticle]:
        """
        Migration bridge: discover + execute all tasks synchronously.
        Kept so existing tests pass while concrete scrapers are being migrated.
        Removed in Task 12 once all scrapers implement discover().
        """
        results = []
        for task in self.discover():
            article = task.execute()
            if article is not None:
                results.append(article)
        return results