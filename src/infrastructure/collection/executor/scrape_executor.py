import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from .fetch_task import FetchTask
from .host_queue_map import HostQueueMap
from .queue_router import QueueRouter
from .queue_selector import (
    QueueSelector,
    WeightedRoundRobinQueueSelector,
)
from src.shared.logging import get_logger
from src.modules.collection.domain.value_objects import ScrapedArticle

logger = get_logger(__name__)


class ScrapeExecutor:
    """
    Two-phase concurrent fetch executor.

    Phase 1 (single-threaded):
      route() — accepts a flat list of FetchTask objects and assigns each
      to a per-host queue via QueueRouter.

    Phase 2 (multi-threaded via ThreadPoolExecutor):
      execute() — spins up num_workers futures.  Each future runs
      _worker_loop(), which repeatedly:
        1. Asks QueueSelector for candidate queue indices (deepest backlog first).
        2. Attempts semaphore.acquire(blocking=False) on each candidate.
        3. On success, dequeues one FetchTask, runs task.execute(), calls
           on_result() with the ScrapedArticle if one was returned.
        4. Releases the semaphore and sleeps `delay` seconds.
        5. Exits when done_flag is True AND all queues are empty.

    Per-host mutual exclusion is guaranteed by BoundedSemaphore(1) — at most
    one concurrent request per host at any time.

    Args:
        num_workers: Number of concurrent worker threads (default 3).
        delay:       Seconds to sleep between requests per worker (default 5.0).
        selector:    QueueSelector strategy (default WeightedRoundRobinQueueSelector).
    """

    def __init__(
        self,
        num_workers: int = 5,
        delay: float = 5.0,
        selector: Optional[QueueSelector] = None,
    ) -> None:
        self._num_workers = num_workers
        self._delay = delay
        self._selector = selector or WeightedRoundRobinQueueSelector()

    def run(
        self,
        tasks: List[FetchTask],
        on_result: Callable[[ScrapedArticle], None],
    ) -> int:
        """
        Route tasks then dispatch workers.  Blocks until all tasks are processed.
        Returns the number of successful ScrapedArticles produced.
        """
        if not tasks:
            return 0

        # ── Phase 1: route into per-host queues ──────────────────────────
        host_queue_map = HostQueueMap()
        router = QueueRouter(host_queue_map)
        router.route(tasks)

        logger.info(
            "executor_phase1_complete",
            total_tasks=len(tasks),
            host_count=len(host_queue_map.queues),
        )

        # ── Phase 2: concurrent fetch ─────────────────────────────────────
        done_flag: list[bool] = [False]   # mutable flag shared with worker closures

        def worker_loop(worker_id: int) -> int:
            logger.info("worker_started", worker_id=worker_id)
            fetched = 0

            while True:
                claimed_idx = self._try_claim(host_queue_map)

                if claimed_idx is None:
                    if done_flag[0] and all(q.empty() for q in host_queue_map.queues):
                        break
                    time.sleep(0.05)
                    continue

                try:
                    try:
                        task = host_queue_map.queues[claimed_idx].get_nowait()
                    except queue.Empty:
                        continue

                    result = task.execute()
                    if result is not None:
                        on_result(result)
                        fetched += 1
                    else:
                        logger.warning("task_returned_none", url=task.url)

                finally:
                    host_queue_map.semaphores[claimed_idx].release()
                    time.sleep(self._delay)

            logger.info("worker_stopped", worker_id=worker_id, fetched=fetched)
            return fetched

        total_fetched = 0
        with ThreadPoolExecutor(max_workers=self._num_workers) as pool:
            futures = [
                pool.submit(worker_loop, i) for i in range(self._num_workers)
            ]
            done_flag[0] = True   # all tasks are queued; workers may now drain and exit

            for future in as_completed(futures):
                try:
                    total_fetched += future.result()
                except Exception as e:
                    logger.error("worker_raised", error=str(e))

        logger.info("executor_phase2_complete", total_fetched=total_fetched)
        return total_fetched

    def _try_claim(self, host_queue_map: HostQueueMap) -> Optional[int]:
        """
        Ask the selector for candidate indices and try to acquire each semaphore
        non-blocking.  Returns the first acquired index, or None.
        """
        for idx in self._selector.select(host_queue_map.queues):
            if host_queue_map.semaphores[idx].acquire(blocking=False):
                if not host_queue_map.queues[idx].empty():
                    return idx
                host_queue_map.semaphores[idx].release()
        return None