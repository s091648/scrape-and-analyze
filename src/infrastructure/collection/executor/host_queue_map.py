import threading
from queue import Queue
from typing import Dict, List


class HostQueueMap:
    """
    Mapping table: hostname (str) → queue index (int).

    Each host gets:
    - A Queue for pending work (holds both DiscoverTask and FetchTask).
    - A BoundedSemaphore(1) for single-thread-per-host mutual exclusion.

    Thread-safe: get_or_create() may be called concurrently by discover
    workers routing new FetchTasks into queues while fetch workers are running.
    """

    def __init__(self) -> None:
        self._map: Dict[str, int] = {}
        self._queues: List[Queue] = []
        self._semaphores: List[threading.BoundedSemaphore] = []
        self._lock = threading.Lock()

    def get_or_create(self, host: str) -> int:
        """Return existing queue index for host, or allocate a new queue + semaphore. Thread-safe."""
        with self._lock:
            if host not in self._map:
                self._map[host] = len(self._queues)
                self._queues.append(Queue())
                self._semaphores.append(threading.BoundedSemaphore(1))
            return self._map[host]

    @property
    def queues(self) -> List[Queue]:
        """Return the list of per-host work queues."""
        return self._queues

    @property
    def semaphores(self) -> List[threading.BoundedSemaphore]:
        """Return the list of per-host BoundedSemaphore(1) for mutual exclusion."""
        return self._semaphores

    @property
    def host_map(self) -> Dict[str, int]:
        """Return a snapshot copy of the hostname-to-queue-index mapping."""
        with self._lock:
            return dict(self._map)
