import contextvars
import queue
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional
from urllib.parse import urlparse

from opentelemetry.trace import StatusCode

from shared.enums.observability import SpanName
from src.infrastructure.shared.observability import get_tracer
from .discover_task import DiscoverTask
from .fetch_task import FetchTask
from .host_queue_map import HostQueueMap
from .queue_router import QueueRouter
from .queue_selector import (
    QueueSelector,
    WeightedRoundRobinQueueSelector,
)
from src.infrastructure.collection.clients.rate_limit_errors import ProviderRateLimitedError
from src.infrastructure.shared.rate_limit_tracker import RateLimitedProviderTracker
from src.shared.logging import get_logger
from src.modules.collection.domain.value_objects import ScrapedArticle


def _context_wrapper(fn, ctx: contextvars.Context):
    """Run *fn* inside a copied context so OTel span state propagates
    into the worker thread.  Python < 3.12 does NOT copy contextvars
    into ThreadPoolExecutor workers automatically."""
    def _run(*args, **kwargs):
        """Execute fn inside the copied context for OTel span propagation."""
        return ctx.run(fn, *args, **kwargs)
    return _run

logger = get_logger(__name__)


class ScrapeExecutor:
    """
    Concurrent discover + fetch executor.

    run_discover()   — discover-only; returns the FetchTasks discovered.
    run_fetch_only() — fetch pre-built FetchTasks.

    CollectionPipeline calls these two separately (each wrapped in
    asyncio.to_thread) rather than interleaving discover and fetch —
    see 024-async-pipeline-refactor FR-003.

    Per-host mutual exclusion is guaranteed by BoundedSemaphore(1) — at most
    one concurrent request per host at any time.

    Args:
        num_workers:       Number of fetch worker threads (default 5).
        discover_workers:  Number of discover worker threads (default 5). Safe to run
                           concurrently with itself — HostQueueMap's per-host
                           BoundedSemaphore(1) already guarantees at most one in-flight
                           discover per host regardless of pool size, so raising this
                           only lets *independent* hosts overlap (e.g. a slow/rate-limited
                           host no longer blocks every other host's discover behind it).
        fetch_delay:       Seconds to sleep between fetches per worker (default 5.0).
        selector:          QueueSelector strategy.
    """

    def __init__(
        self,
        num_workers: int = 5,
        discover_workers: int = 5,
        fetch_delay: float = 5.0,
        selector: Optional[QueueSelector] = None,
        on_discover_failed: Optional[Callable] = None,
    ) -> None:
        self._num_workers = num_workers
        self._discover_workers = discover_workers
        self._fetch_delay = fetch_delay
        self._selector = selector or WeightedRoundRobinQueueSelector()
        self._on_discover_failed = on_discover_failed
        self._rate_limit_tracker = RateLimitedProviderTracker()

    @property
    def exhausted_hosts(self) -> List[str]:
        """Hostnames that hit ProviderRateLimitedError during discover this run —
        surfaced so callers (main.py) can report it in the pipeline completion
        notification alongside LLM-provider rate limits."""
        return self._rate_limit_tracker.exhausted

    # ── Discover-only mode ────────────────────────────────────────────────

    def run_discover(
        self,
        discover_tasks: List[DiscoverTask],
        pre_fetch_filter: Optional[Callable[[List[FetchTask]], List[FetchTask]]] = None,
    ) -> List[FetchTask]:
        """
        Discover-only mode: execute all discover tasks and return resulting FetchTasks.

        Does NOT fetch — caller should pass the returned FetchTasks to run_fetch_only().
        """
        if not discover_tasks:
            return []

        host_queue_map = HostQueueMap()
        router = QueueRouter(host_queue_map)
        router.route_discover(discover_tasks)

        # Dynamic sizing (not a fixed constant): never spin up more worker
        # threads than there are distinct hosts to discover this run — a
        # worker beyond that count would just poll queues every other
        # worker already holds the (per-host BoundedSemaphore(1)) lock on,
        # since HostQueueMap allocates exactly one queue+semaphore per host.
        # self._discover_workers is a ceiling, not a target: few due sources
        # this run means few threads spun up; many distinct hosts due at
        # once can still use up to that ceiling in parallel.
        worker_count = min(self._discover_workers, len(host_queue_map.queues))

        logger.info(
            "executor_discover_start",
            discover_tasks=len(discover_tasks),
            host_count=len(host_queue_map.queues),
            discover_workers=worker_count,
        )

        pending_discovers = [len(discover_tasks)]
        pending_lock = threading.Lock()

        def _on_discover_complete():
            """Decrement the pending discover counter after a discover finishes."""
            with pending_lock:
                pending_discovers[0] -= 1

        all_fetch_tasks: List[FetchTask] = []

        def _route_and_collect(fetch_tasks: List[FetchTask]) -> int:
            """Apply pre-fetch filter, collect fetch tasks, and route them into host queues.
            Returns the number of fetch tasks that survived the filter (i.e. not
            already-analyzed duplicates) — the caller uses this to report
            discover.new_count/discover.duplicate_count on that discover's own span."""
            if pre_fetch_filter is not None:
                fetch_tasks = pre_fetch_filter(fetch_tasks)
            all_fetch_tasks.extend(fetch_tasks)
            router.route(fetch_tasks)
            return len(fetch_tasks)

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = []
            for i in range(worker_count):
                futures.append(pool.submit(
                    _context_wrapper(self._discover_worker_loop_collect, contextvars.copy_context()),
                    worker_id=i,
                    host_queue_map=host_queue_map,
                    router=router,
                    pending_discovers=pending_discovers,
                    pending_lock=pending_lock,
                    on_discover_complete=_on_discover_complete,
                    on_fetch_tasks=_route_and_collect,
                ))
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error("discover_worker_raised", error=str(e))

        logger.info("executor_discover_complete", fetch_tasks=len(all_fetch_tasks))
        return all_fetch_tasks

    def _discover_worker_loop_collect(
        self,
        worker_id: int,
        host_queue_map: HostQueueMap,
        router: QueueRouter,
        pending_discovers: list,
        pending_lock: threading.Lock,
        on_discover_complete: Callable[[], None],
        on_fetch_tasks: Callable[[List[FetchTask]], int],
    ) -> int:
        """Discover worker that collects FetchTasks via callback instead of routing to queues."""
        logger.info("discover_worker_started", worker_id=worker_id)
        discover_count = 0

        while True:
            claimed_idx = self._try_claim(host_queue_map)

            if claimed_idx is None:
                with pending_lock:
                    if pending_discovers[0] <= 0 and all(
                        q.empty() for q in host_queue_map.queues
                    ):
                        break
                time.sleep(0.05)
                continue

            try:
                try:
                    task = host_queue_map.queues[claimed_idx].get_nowait()
                except queue.Empty:
                    continue

                if isinstance(task, DiscoverTask):
                    host = self._host_for_queue(host_queue_map, claimed_idx)

                    is_aborted = self._rate_limit_tracker.is_exhausted(host)

                    if is_aborted:
                        logger.warning(
                            "discover_skipped_aborted_host",
                            source=task.setting.source,
                            host=host,
                        )
                        if self._on_discover_failed is not None:
                            self._on_discover_failed(
                                task,
                                ProviderRateLimitedError("Skipped: host previously rate-limited this run"),
                            )
                        on_discover_complete()
                    else:
                        with get_tracer().start_as_current_span(SpanName.DISCOVER_TASK) as span:
                            span.set_attribute("discover.source", task.setting.source)
                            span.set_attribute("discover.host", host)
                            try:
                                fetch_tasks = task.execute()
                                discover_count += 1
                                discovered_count = len(fetch_tasks) if fetch_tasks else 0
                                span.set_attribute("discover.discovered_count", discovered_count)

                                if fetch_tasks:
                                    new_count = on_fetch_tasks(fetch_tasks)
                                    span.set_attribute("discover.new_count", new_count)
                                    span.set_attribute("discover.duplicate_count", discovered_count - new_count)
                                    logger.info(
                                        "discover_produced_fetch_tasks",
                                        source=task.setting.source,
                                        host=task.host,
                                        count=len(fetch_tasks),
                                    )
                                else:
                                    span.set_attribute("discover.new_count", 0)
                                    span.set_attribute("discover.duplicate_count", 0)
                            except ProviderRateLimitedError as exc:
                                self._rate_limit_tracker.mark_exhausted(host)
                                span.set_status(StatusCode.ERROR, "rate_limited")
                                logger.warning(
                                    "discover_rate_limited_host_aborted",
                                    host=host,
                                    source=task.setting.source,
                                )
                                if self._on_discover_failed is not None:
                                    self._on_discover_failed(task, exc)
                            finally:
                                on_discover_complete()

            finally:
                # Per-host politeness is fully owned by DomainRateLimiter now
                # (src/infrastructure/shared/http/rate_limiter.py) — it's wired
                # into every HttpClient call (discover AND fetch alike, whichever
                # phase makes it), stateful for the whole run, and blocks the
                # actual HTTP call itself rather than an executor-level guess at
                # how long to wait. No extra cooldown needed here on top of that.
                host_queue_map.semaphores[claimed_idx].release()

        logger.info("discover_worker_stopped", worker_id=worker_id, discovers=discover_count)
        return 0

    # ── Fetch-only mode ──────────────────────────────────────────────────

    def run_fetch_only(
        self,
        fetch_tasks: List[FetchTask],
        on_result: Callable[[ScrapedArticle], None],
    ) -> int:
        """
        Fetch-only mode: route pre-built FetchTasks into per-host queues
        and run fetch workers. Returns count of successful ScrapedArticles.
        """
        if not fetch_tasks:
            return 0

        host_queue_map = HostQueueMap()
        router = QueueRouter(host_queue_map)
        router.route(fetch_tasks)

        logger.info(
            "executor_fetch_start",
            total_tasks=len(fetch_tasks),
            host_count=len(host_queue_map.queues),
        )

        result = self._run_fetch_workers(host_queue_map, on_result)
        logger.info("executor_fetch_complete", total_fetched=result)
        return result

    # ── Fetch-only worker pool (backward compatible) ────────────────────

    def _run_fetch_workers(
        self,
        host_queue_map: HostQueueMap,
        on_result: Callable[[ScrapedArticle], None],
    ) -> int:
        """Spawn fetch worker threads and block until all tasks are processed."""
        done_flag: list[bool] = [False]
        total_fetched = 0

        def worker_loop(worker_id: int) -> int:
            """Fetch worker: claim queues, execute FetchTasks, and collect results."""
            logger.info("worker_started", worker_id=worker_id)
            fetched = 0

            while True:
                claimed_idx = self._try_claim(host_queue_map)

                if claimed_idx is None:
                    if done_flag[0]:
                        final_idx = self._try_claim(host_queue_map)
                        if final_idx is not None:
                            host_queue_map.semaphores[final_idx].release()
                            time.sleep(0.01)
                            continue
                        break
                    time.sleep(0.05)
                    continue

                try:
                    try:
                        task = host_queue_map.queues[claimed_idx].get_nowait()
                    except queue.Empty:
                        continue

                    if isinstance(task, FetchTask):
                        try:
                            result = task.execute()
                            if result is not None:
                                on_result(result)
                                fetched += 1
                            else:
                                logger.warning("task_returned_none", url=task.url)
                        except Exception as e:
                            logger.error("task_execute_failed", url=task.url, error=str(e))

                finally:
                    time.sleep(self._fetch_delay)
                    host_queue_map.semaphores[claimed_idx].release()

            logger.info("worker_stopped", worker_id=worker_id, fetched=fetched)
            return fetched

        with ThreadPoolExecutor(max_workers=self._num_workers) as pool:
            futures = [
                pool.submit(_context_wrapper(worker_loop, contextvars.copy_context()), i)
                for i in range(self._num_workers)
            ]
            done_flag[0] = True

            for future in as_completed(futures):
                try:
                    total_fetched += future.result()
                except Exception as e:
                    logger.error("worker_raised", error=str(e))

        logger.info("executor_phase2_complete", total_fetched=total_fetched)
        return total_fetched

    # ── Shared helpers ──────────────────────────────────────────────────

    def _try_claim(self, host_queue_map: HostQueueMap) -> Optional[int]:
        """Attempt to acquire a non-empty queue's semaphore; returns queue index or None."""
        for idx in self._selector.select(host_queue_map.queues):
            if host_queue_map.semaphores[idx].acquire(blocking=False):
                if not host_queue_map.queues[idx].empty():
                    return idx
                host_queue_map.semaphores[idx].release()
        return None

    @staticmethod
    def _host_for_queue(host_queue_map: HostQueueMap, idx: int) -> str:
        """Reverse-lookup host name from queue index."""
        for host, i in host_queue_map.host_map.items():
            if i == idx:
                return host
        return ""
