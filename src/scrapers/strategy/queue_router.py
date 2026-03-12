from typing import List
from urllib.parse import urlparse

from src.scrapers.strategy.host_queue_map import HostQueueMap
from src.scrapers.strategy.scrape_task import ScrapeTask
from src.utils.logging import get_logger

logger = get_logger(__name__)


class QueueRouter:
    """
    Routes ScrapeTask objects into per-host queues in a HostQueueMap.
    Called once during Phase 1 (single-threaded) — not thread-safe.
    """

    def __init__(self, host_queue_map: HostQueueMap) -> None:
        self._map = host_queue_map

    def route(self, tasks: List[ScrapeTask]) -> None:
        """Assign each task to its host's queue."""
        for task in tasks:
            host = self._extract_host(task.url)
            idx = self._map.get_or_create(host)
            self._map.queues[idx].put(task)
            logger.debug("task_routed", url=task.url, host=host, queue_idx=idx)

    @staticmethod
    def _extract_host(url: str) -> str:
        """Return netloc from URL; fall back to the raw string if parsing fails."""
        try:
            netloc = urlparse(url).netloc
            return netloc if netloc else url
        except Exception:
            return url