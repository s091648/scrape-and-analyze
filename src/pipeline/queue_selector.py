from abc import ABC, abstractmethod
from queue import Queue
from typing import List

from src.pipeline.task import ScrapeTask


class QueueSelector(ABC):
    """
    Strategy interface for ordering queue candidates for an idle worker.

    select() returns non-empty queue indices in preferred order.
    The worker iterates the list and attempts semaphore.acquire(blocking=False)
    on each index — first successful acquire wins.

    Implementations only express ordering preference; mutual exclusion is
    enforced by the per-queue BoundedSemaphore(1) in HostQueueMap.
    """

    @abstractmethod
    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        """
        Return indices of non-empty queues in preferred processing order.
        Returns [] if all queues are empty.
        """
        pass


class RoundRobinQueueSelector(QueueSelector):
    """
    Returns non-empty queue indices starting from a rotating offset.
    Provides fair distribution across hosts regardless of queue depth.
    """

    def __init__(self) -> None:
        self._counter: int = 0

    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        n = len(queues)
        if n == 0:
            return []
        start = self._counter % n
        self._counter += 1
        ordered = [(start + i) % n for i in range(n)]
        return [idx for idx in ordered if not queues[idx].empty()]


class WeightedRoundRobinQueueSelector(QueueSelector):
    """
    Returns non-empty queue indices sorted by queue depth descending.
    Prioritises draining the deepest backlog first.
    This is the default selector.
    """

    def select(self, queues: List[Queue[ScrapeTask]]) -> List[int]:
        candidates = [
            (i, queues[i].qsize())
            for i in range(len(queues))
            if not queues[i].empty()
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in candidates]
