from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ScrapedArticle:
    """Data class representing a scraped article"""
    url: str
    title: str
    content: str
    published_at: Optional[str]
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseScraper(ABC):
    """Abstract base class for all scrapers"""

    @abstractmethod
    def scrape(self) -> List[ScrapedArticle]:
        """Scrape and return list of articles"""
        pass
