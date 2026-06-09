from dataclasses import dataclass
from typing import Any, List

from .fetch_task import FetchTask
from src.infrastructure.collection.clients.arxiv_client import ArxivRateLimitedError
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoverTask:
    """
    A unit of discover work for a single source setting.

    On execute(), calls scraper.discover() and wraps the resulting
    ScrapeJobs into FetchTask objects that can be routed back into
    the per-host queue for fetching.

    setting — the ScraperSetting that triggered this discover.
    scraper — the BaseScraper instance for this source.
    host    — the hostname discover requests will hit (for queue routing).
    """
    setting: Any
    scraper: Any
    host: str

    def execute(self) -> List[FetchTask]:
        """Run scraper.discover() and return the resulting FetchTask list; empty list on failure."""
        try:
            jobs = self.scraper.discover()
        except ArxivRateLimitedError:
            raise
        except Exception as e:
            logger.error(
                "discover_failed",
                source=self.setting.source,
                error=str(e),
            )
            return []

        return [
            FetchTask(
                url=j.url,
                source=j.source,
                job=j,
                scraper=self.scraper,
            )
            for j in jobs
        ]
