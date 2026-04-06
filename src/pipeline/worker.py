import queue
import threading
import time
from typing import Callable, Optional

from src.ingestion.models.scraped_article import ScrapedArticle
from src.pipeline.host_queue_map import HostQueueMap
from src.pipeline.queue_selector import QueueSelector
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScraperWorker(threading.Thread):
    """
    Worker thread that processes ScrapeTask objects from host queues.

    Mutual exclusion per host is enforced by BoundedSemaphore(1) in HostQueueMap.
    No shared lock or busy-set is needed.

    Claiming a queue:
        1. Ask QueueSelector for ordered candidate indices (non-empty queues).
        2. For each candidate, attempt semaphore.acquire(blocking=False).
        3. First successful acquire → worker owns that queue slot.
        4. If the queue is somehow empty after acquiring (defensive), release immediately.

    Termination:
        Caller sets done_event after all tasks are in queues.
        Worker exits when done_event is set AND all queues are empty.

    Delay:
        Applied after each task, outside the semaphore, to rate-limit requests per host.
    """

    def __init__(
        self,
        worker_id: int,
        host_queue_map: HostQueueMap,
        selector: QueueSelector,
        done_event: threading.Event,
        on_result: Callable[[ScrapedArticle], None],
        delay: float = 5.0,
    ) -> None:
        super().__init__(daemon=True, name=f"ScraperWorker-{worker_id}")
        self._id = worker_id
        self._qmap = host_queue_map
        self._selector = selector
        self._done_event = done_event
        self._on_result = on_result
        self._delay = delay

    def run(self) -> None:
        logger.info("worker_started", worker_id=self._id)
        while True:
            claimed_idx = self._try_claim_queue()

            if claimed_idx is None:
                if self._done_event.is_set() and self._all_empty():
                    break
                self._done_event.wait(timeout=0.1)
                continue

            try:
                try:
                    task = self._qmap.queues[claimed_idx].get_nowait()
                except queue.Empty:
                    continue

                result = task.execute()
                if result is not None:
                    self._on_result(result)

            finally:
                self._qmap.semaphores[claimed_idx].release()
                time.sleep(self._delay)

        logger.info("worker_stopped", worker_id=self._id)

    def _try_claim_queue(self) -> Optional[int]:
        for idx in self._selector.select(self._qmap.queues):
            if self._qmap.semaphores[idx].acquire(blocking=False):
                if not self._qmap.queues[idx].empty():
                    return idx
                self._qmap.semaphores[idx].release()
        return None

    def _all_empty(self) -> bool:
        return all(q.empty() for q in self._qmap.queues)
