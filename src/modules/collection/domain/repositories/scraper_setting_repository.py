from abc import ABC, abstractmethod
from typing import List
from uuid import UUID

from src.modules.collection.domain.entities import ScraperSetting


class ScraperSettingRepository(ABC):
    """Abstract repository for accessing and updating ScraperSetting entities."""

    @abstractmethod
    def get_active_due(self) -> List[ScraperSetting]:
        """Return all active ScraperSettings whose scrape interval has elapsed."""

    @abstractmethod
    def mark_scraped(self, setting_id: UUID) -> None:
        """Update last_scraped_at to now for the given setting."""
