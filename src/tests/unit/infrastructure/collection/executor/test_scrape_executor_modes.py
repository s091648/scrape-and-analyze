"""
Tests for the new ScrapeExecutor modes added in PR #60:
  - run_discover()          — discover-only; returns FetchTasks
  - run_fetch_only()        — fetch pre-built FetchTasks
  - _discover_worker_loop_collect — used internally by run_discover
"""
import queue as queue_module
from unittest.mock import MagicMock

from src.infrastructure.collection.executor.discover_task import DiscoverTask
from src.infrastructure.collection.executor.fetch_task import FetchTask
from src.infrastructure.collection.executor.host_queue_map import HostQueueMap
from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor
from src.infrastructure.collection.clients.arxiv_client import ArxivRateLimitedError
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_setting(source: str) -> MagicMock:
    s = MagicMock()
    s.source = source
    return s


def _make_discover_task(source: str, host: str, articles: list) -> DiscoverTask:
    jobs = [ScrapeJob(url=a.url, source=source, source_type="rss") for a in articles]
    scraper = MagicMock()
    scraper.discover.return_value = jobs
    scraper.fetch.side_effect = articles
    return DiscoverTask(setting=_make_setting(source), scraper=scraper, host=host)


def _make_fetch_task(url: str, source: str) -> FetchTask:
    article = ScrapedArticle(url=url, title="T", content="C", source=source)
    scraper = MagicMock()
    scraper.fetch.return_value = article
    job = ScrapeJob(url=url, source=source, source_type="rss")
    return FetchTask(url=url, source=source, job=job, scraper=scraper)


# ── run_discover ───────────────────────────────────────────────────────────────

def test_run_discover_returns_empty_list_for_no_discover_tasks():
    executor = ScrapeExecutor(discover_workers=1, fetch_delay=0.0)
    result = executor.run_discover([])
    assert result == []


def test_run_discover_returns_fetch_tasks_from_all_sources():
    articles_a = [
        ScrapedArticle(url="https://a.com/1", title="A1", content="C", source="src-a"),
        ScrapedArticle(url="https://a.com/2", title="A2", content="C", source="src-a"),
    ]
    articles_b = [
        ScrapedArticle(url="https://b.com/1", title="B1", content="C", source="src-b"),
    ]
    task_a = _make_discover_task("src-a", "a.com", articles_a)
    task_b = _make_discover_task("src-b", "b.com", articles_b)

    executor = ScrapeExecutor(discover_workers=1, fetch_delay=0.0)
    fetch_tasks = executor.run_discover([task_a, task_b])

    urls = {ft.url for ft in fetch_tasks}
    assert urls == {"https://a.com/1", "https://a.com/2", "https://b.com/1"}


def test_run_discover_applies_pre_fetch_filter():
    articles = [
        ScrapedArticle(url="https://src.com/keep", title="Keep", content="C", source="src"),
        ScrapedArticle(url="https://src.com/drop", title="Drop", content="C", source="src"),
    ]
    task = _make_discover_task("src", "src.com", articles)

    def _filter(tasks: list) -> list:
        return [t for t in tasks if "keep" in t.url]

    executor = ScrapeExecutor(discover_workers=1, fetch_delay=0.0)
    fetch_tasks = executor.run_discover([task], pre_fetch_filter=_filter)

    urls = [ft.url for ft in fetch_tasks]
    assert urls == ["https://src.com/keep"]


def test_run_discover_calls_on_discover_failed_on_rate_limit():
    scraper = MagicMock()
    scraper.discover.side_effect = ArxivRateLimitedError("429")
    task = DiscoverTask(setting=_make_setting("arxiv"), scraper=scraper, host="export.arxiv.org")

    failed = []
    executor = ScrapeExecutor(
        discover_workers=1,
        fetch_delay=0.0,
        on_discover_failed=lambda t, exc: failed.append(t.setting.source),
    )
    fetch_tasks = executor.run_discover([task])

    assert fetch_tasks == []
    assert "arxiv" in failed


def test_run_discover_calls_on_discover_failed_for_aborted_host():
    scraper1 = MagicMock()
    scraper1.discover.side_effect = ArxivRateLimitedError("429")
    scraper2 = MagicMock()
    scraper2.discover.return_value = []

    task1 = DiscoverTask(setting=_make_setting("arxiv-1"), scraper=scraper1, host="export.arxiv.org")
    task2 = DiscoverTask(setting=_make_setting("arxiv-2"), scraper=scraper2, host="export.arxiv.org")

    failed = []
    executor = ScrapeExecutor(
        discover_workers=1,
        fetch_delay=0.0,
        on_discover_failed=lambda t, exc: failed.append(t.setting.source),
    )
    executor.run_discover([task1, task2])

    # Both tasks are reported as failed
    assert len(failed) == 2
    scraper2.discover.assert_not_called()


# ── run_fetch_only ─────────────────────────────────────────────────────────────

def test_run_fetch_only_returns_zero_for_empty_list():
    executor = ScrapeExecutor(num_workers=1, fetch_delay=0.0)
    assert executor.run_fetch_only([], on_result=lambda _: None) == 0


def test_run_fetch_only_executes_all_tasks_and_calls_on_result():
    tasks = [
        _make_fetch_task("https://a.com/1", "src"),
        _make_fetch_task("https://a.com/2", "src"),
        _make_fetch_task("https://b.com/1", "src"),
    ]
    collected = []
    executor = ScrapeExecutor(num_workers=2, fetch_delay=0.0)
    total = executor.run_fetch_only(tasks, on_result=collected.append)

    assert total == 3
    assert len(collected) == 3
    urls = {a.url for a in collected}
    assert urls == {"https://a.com/1", "https://a.com/2", "https://b.com/1"}


def test_run_fetch_only_handles_task_exception_gracefully():
    scraper = MagicMock()
    scraper.fetch.side_effect = RuntimeError("fetch failed")
    job = ScrapeJob(url="https://fail.com/1", source="src", source_type="rss")
    bad_task = FetchTask(url="https://fail.com/1", source="src", job=job, scraper=scraper)

    collected = []
    executor = ScrapeExecutor(num_workers=1, fetch_delay=0.0)
    total = executor.run_fetch_only([bad_task], on_result=collected.append)

    assert total == 0
    assert collected == []


def test_run_fetch_only_handles_on_result_exception_gracefully():
    """FetchTask.execute() itself swallows its own scraper errors (returns
    None) — the only way the fetch worker's outer except Exception (which
    records the OTel span as ERROR) fires for a real FetchTask is a failure
    in on_result() itself, after a successful fetch."""
    tasks = [_make_fetch_task("https://boom.com/1", "src")]

    def _raising_on_result(article):
        raise RuntimeError("on_result blew up")

    executor = ScrapeExecutor(num_workers=1, fetch_delay=0.0)
    total = executor.run_fetch_only(tasks, on_result=_raising_on_result)

    # The task's own fetch succeeded; on_result's failure doesn't count it,
    # but must not crash the worker or the run.
    assert total == 0


def test_fetch_worker_handles_queue_empty_race_after_claim():
    """Defensive path: _try_claim() confirmed the queue non-empty and holds
    its semaphore, but another thread could in principle still have drained
    it before get_nowait() runs — the worker must catch queue.Empty, record
    it on the span, and move on instead of crashing."""
    class _RacyQueue:
        """Reports non-empty once (so _try_claim claims it), then raises
        queue.Empty from get_nowait() — simulating the race — and reports
        empty afterwards so the worker loop can cleanly terminate.
        qsize() is needed too — WeightedRoundRobinQueueSelector (the default
        selector) calls it to rank candidates before _try_claim ever checks
        empty()/get_nowait()."""
        def __init__(self):
            self._raised = False

        def empty(self):
            return self._raised

        def qsize(self):
            return 0 if self._raised else 1

        def get_nowait(self):
            self._raised = True
            raise queue_module.Empty()

    host_queue_map = HostQueueMap()
    idx = host_queue_map.get_or_create("racy.com")
    host_queue_map.queues[idx] = _RacyQueue()

    executor = ScrapeExecutor(num_workers=1, fetch_delay=0.0)
    collected = []
    total = executor._run_fetch_workers(host_queue_map, on_result=collected.append)

    assert total == 0
    assert collected == []


def test_run_fetch_only_skips_none_results():
    scraper = MagicMock()
    scraper.fetch.return_value = None
    job = ScrapeJob(url="https://none.com/1", source="src", source_type="rss")
    null_task = FetchTask(url="https://none.com/1", source="src", job=job, scraper=scraper)

    collected = []
    executor = ScrapeExecutor(num_workers=1, fetch_delay=0.0)
    total = executor.run_fetch_only([null_task], on_result=collected.append)

    assert total == 0
    assert collected == []


# ── run_discover + run_fetch_only pipeline ────────────────────────────────────

def test_discover_then_fetch_only_pipeline():
    """Two-phase pipeline: discover → filter → fetch_only."""
    articles = [
        ScrapedArticle(url="https://src.com/a", title="A", content="C", source="src"),
        ScrapedArticle(url="https://src.com/b", title="B", content="C", source="src"),
    ]
    task = _make_discover_task("src", "src.com", articles)

    executor = ScrapeExecutor(num_workers=1, discover_workers=1, fetch_delay=0.0)
    fetch_tasks = executor.run_discover([task])
    assert len(fetch_tasks) == 2

    collected = []
    total = executor.run_fetch_only(fetch_tasks, on_result=collected.append)
    assert total == 2
    assert len(collected) == 2
