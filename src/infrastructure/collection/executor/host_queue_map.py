import threading
from queue import Queue
from typing import Dict, List

from .fetch_task import FetchTask


class HostQueueMap:
    """
    Mapping table: hostname (str) → queue index (int).

    Each host gets:
    - A Queue[FetchTask] for pending work.
    - A BoundedSemaphore(1) for single-thread-per-host mutual exclusion.

    Created fresh per pipeline run.
    get_or_create() is NOT thread-safe — call only from the single-threaded
    Phase 1 (routing) before workers start.
    """

    def __init__(self) -> None:
        self._map: Dict[str, int] = {}
        self._queues: List[Queue[FetchTask]] = []
        self._semaphores: List[threading.BoundedSemaphore] = []

    def get_or_create(self, host: str) -> int:
        """Return existing queue index for host, or allocate a new queue + semaphore."""
        if host not in self._map:
            self._map[host] = len(self._queues)
            self._queues.append(Queue())
            self._semaphores.append(threading.BoundedSemaphore(1))
        return self._map[host]

    @property
    def queues(self) -> List[Queue[FetchTask]]:
        return self._queues

    @property
    def semaphores(self) -> List[threading.BoundedSemaphore]:
        return self._semaphores

    @property
    def host_map(self) -> Dict[str, int]:
        return dict(self._map)
