from abc import abstractmethod
from typing import List, Optional

from src.modules.collection.domain.services import Scraper
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle


class BaseScraper(Scraper):
    """
    Infrastructure base for all scrapers.
    Extends the domain Scraper interface with a fetch() method so that
    the same instance can both discover URLs and retrieve article content.
    """

    @abstractmethod
    def discover(self) -> List[ScrapeJob]:
        """Enumerate pending ScrapeJobs for this source."""
        ...

    @abstractmethod
    def fetch(self, job: ScrapeJob) -> Optional[ScrapedArticle]:
        """
        Fetch full article content for *job* and return a ScrapedArticle.
        Returns None on any failure.
        """
        ...