from abc import ABC, abstractmethod
from typing import List

from src.modules.collection.domain.entities import ScrapeJob


class Scraper(ABC):
    """Domain interface for discovering scrape jobs from a source."""

    @abstractmethod
    def discover(self) -> List[ScrapeJob]:
        """
        Enumerate all pending work items for this source.
        Makes the minimum requests needed to find article URLs.
        Returns [] on any failure.
        """
        ...
