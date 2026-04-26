from abc import ABC, abstractmethod
from typing import List, Optional

from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle


class Scraper(ABC):
    """Domain interface for discovering and fetching scrape jobs from a source."""

    @abstractmethod
    def discover(self) -> List[ScrapeJob]:
        """
        Enumerate all pending work items for this source.
        Makes the minimum requests needed to find article URLs.
        Returns [] on any failure.
        """
        ...

    @abstractmethod
    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """
        Fetch full article content for *job*.
        Returns None on any failure.
        """
        ...