from abc import ABC, abstractmethod

from src.modules.collection.domain.entities import ScraperSetting
from src.modules.collection.domain.services import Scraper


class ScraperFactory(ABC):
    """Domain interface for creating the appropriate Scraper for a given ScraperSetting."""

    @abstractmethod
    def create_for(self, setting: ScraperSetting) -> Scraper:
        """Return a configured Scraper instance for *setting*."""
        ...
