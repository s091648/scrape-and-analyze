import threading
from typing import Callable, List, Optional

from src.scrapers.scrapers.article import ScrapedArticle
from src.scrapers.scrapers.base_scraper import BaseScraper
from src.scrapers.strategy.host_queue_map import HostQueueMap
from src.scrapers.strategy.queue_router import QueueRouter
from src.scrapers.strategy.queue_selector import QueueSelector, WeightedRoundRobinQueueSelector
from src.scrapers.strategy.worker import ScraperWorker
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScrapeDispatcher:
    """
    Orchestrates a full scrape job in two phases.

    Phase 1 (single-threaded):
      Call discover() on each scraper → route tasks into per-host queues.

    Phase 2 (multi-threaded):
      Spin up num_workers ScraperWorker threads.
      Each worker asks QueueSelector for candidates, acquires the first
      available BoundedSemaphore(1), processes one task, sleeps `delay` seconds.

    Args:
        num_workers: Number of concurrent worker threads (default 3).
        delay:       Seconds between requests per worker (default 5.0).
        selector:    QueueSelector instance. Defaults to WeightedRoundRobinQueueSelector.
    """

    def __init__(
        self,
        num_workers: int = 3,
        delay: float = 5.0,
        selector: Optional[QueueSelector] = None,
    ) -> None:
        self._num_workers = num_workers
        self._delay = delay
        self._selector = selector or WeightedRoundRobinQueueSelector()

    def run(
        self,
        scrapers: List[BaseScraper],
        on_result: Callable[[ScrapedArticle], None],
    ) -> None:
        """
        Discover tasks from all scrapers, route them, dispatch workers.
        Blocks until all tasks are processed.
        """
        # ── Phase 1: discover & route ────────────────────────────────────
        host_queue_map = HostQueueMap()
        router = QueueRouter(host_queue_map)
        total_tasks = 0

        for scraper in scrapers:
            try:
                tasks = scraper.discover()
            except Exception as e:
                logger.error("discover_failed",
                             scraper=type(scraper).__name__, error=str(e))
                tasks = []
            router.route(tasks)
            total_tasks += len(tasks)

        logger.info("dispatch_phase1_complete",
                    total_tasks=total_tasks,
                    host_count=len(host_queue_map.queues))

        if total_tasks == 0:
            return

        # ── Phase 2: workers ─────────────────────────────────────────────
        done_event = threading.Event()

        workers = [
            ScraperWorker(
                worker_id=i,
                host_queue_map=host_queue_map,
                selector=self._selector,
                done_event=done_event,
                on_result=on_result,
                delay=self._delay,
            )
            for i in range(self._num_workers)
        ]

        for w in workers:
            w.start()

        # Signal that no more tasks will be added.
        # Workers use this + all_empty() as their exit condition.
        done_event.set()

        for w in workers:
            w.join()

        logger.info("dispatch_phase2_complete")