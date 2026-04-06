"""
Abstract repository interface for ScraperSetting queries.

Returns plain dicts (not domain entities) because scraper settings are
configuration data, not core business objects.  A future phase can
introduce a ScraperSettingEntity if that changes.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ScraperSettingRepository(ABC):

    @abstractmethod
    def get_sources_due(self) -> List[Dict[str, Any]]:
        """Return active sources whose scrape interval has elapsed."""
