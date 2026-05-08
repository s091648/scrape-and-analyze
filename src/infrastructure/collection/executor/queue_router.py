from typing import List
from urllib.parse import urlparse

from .host_queue_map import HostQueueMap
from src.shared.logging import get_logger

logger = get_logger(__name__)


class QueueRouter:
    """
    Routes tasks into per-host queues in a HostQueueMap.

    route()         — route FetchTask objects by URL host.
    route_discover() — route DiscoverTask objects by their explicit host field.

    Both are safe to call concurrently after workers start (HostQueueMap is thread-safe).
    """

    def __init__(self, host_queue_map: HostQueueMap) -> None:
        self._map = host_queue_map

    def route(self, tasks: List) -> None:
        """Assign each FetchTask to its URL host's queue."""
        for task in tasks:
            host = self._extract_host(task.url)
            idx = self._map.get_or_create(host)
            self._map.queues[idx].put(task)
            logger.debug("task_routed", url=task.url, host=host, queue_idx=idx)

    def route_discover(self, tasks: List) -> None:
        """Assign each DiscoverTask to its host's queue."""
        for task in tasks:
            idx = self._map.get_or_create(task.host)
            self._map.queues[idx].put(task)
            logger.debug("discover_routed", host=task.host, queue_idx=idx)

    @staticmethod
    def _extract_host(url: str) -> str:
        """Return netloc from URL; fall back to the raw string if parsing fails."""
        try:
            netloc = urlparse(url).netloc
            return netloc if netloc else url
        except Exception:
            return url
