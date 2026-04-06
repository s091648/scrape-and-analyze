from abc import ABC, abstractmethod
from typing import List

from src.ingestion.models.scraped_article import ScrapedArticle
from src.pipeline.task import ScrapeTask

__all__ = ["BaseScraper", "ScrapedArticle"]


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    @abstractmethod
    def discover(self) -> List[ScrapeTask]:
        """
        Enumerate all work items for this source.
        Makes the minimum HTTP requests needed to find article URLs.
        Returns [] on any failure.
        """
        pass
