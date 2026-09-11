"""
FR-011: When ArxivRateLimitedError is received during discover, the ScrapeExecutor
aborts all remaining discover tasks for that host in the current run.
"""
from unittest.mock import MagicMock

from src.infrastructure.collection.executor.discover_task import DiscoverTask
from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor
from src.infrastructure.collection.clients.arxiv_client import ArxivRateLimitedError
from src.modules.collection.domain.entities import ScrapeJob


def _make_setting(source: str) -> MagicMock:
    s = MagicMock()
    s.source = source
    return s


def test_executor_aborts_remaining_arxiv_discovers_after_429():
    """FR-011: Second discover for same host is never called after first raises 429,
    and the host is surfaced via exhausted_hosts for the completion notification."""
    scraper1 = MagicMock()
    scraper1.discover.side_effect = ArxivRateLimitedError("429 Too Many Requests")

    scraper2 = MagicMock()
    scraper2.discover.return_value = []  # would succeed if called

    task1 = DiscoverTask(setting=_make_setting("arxiv-a"), scraper=scraper1,
                         host="export.arxiv.org")
    task2 = DiscoverTask(setting=_make_setting("arxiv-b"), scraper=scraper2,
                         host="export.arxiv.org")

    failed_tasks = []

    executor = ScrapeExecutor(
        num_workers=1,
        discover_workers=1,
        fetch_delay=0.0,
        on_discover_failed=lambda task, exc: failed_tasks.append(task.setting.source),
    )
    executor.run_discover([task1, task2])

    # Second scraper must never be invoked — host is in the rate-limit tracker
    scraper2.discover.assert_not_called()
    # Both tasks reported as failed (first: real 429; second: skipped)
    assert len(failed_tasks) == 2
    assert "arxiv-a" in failed_tasks
    assert "arxiv-b" in failed_tasks
    # Surfaced publicly so callers (main.py) can report it in the completion notification
    assert executor.exhausted_hosts == ["export.arxiv.org"]


def test_executor_non_arxiv_source_unaffected_by_arxiv_429():
    """FR-011: ArXiv 429 abort is scoped to the arXiv host; other hosts' discovers still run."""
    arxiv_scraper = MagicMock()
    arxiv_scraper.discover.side_effect = ArxivRateLimitedError("429")

    rss_job = ScrapeJob(url="https://techcrunch.com/article", source="rss", source_type="rss")
    rss_scraper = MagicMock()
    rss_scraper.discover.return_value = [rss_job]

    arxiv_task = DiscoverTask(setting=_make_setting("arxiv"), scraper=arxiv_scraper,
                              host="export.arxiv.org")
    rss_task = DiscoverTask(setting=_make_setting("techcrunch"), scraper=rss_scraper,
                            host="techcrunch.com")

    executor = ScrapeExecutor(
        num_workers=2,
        discover_workers=1,
        fetch_delay=0.0,
        on_discover_failed=lambda *_: None,
    )
    fetch_tasks = executor.run_discover([arxiv_task, rss_task])

    # RSS source must have produced its fetch task despite the arXiv 429
    rss_scraper.discover.assert_called_once()
    assert [ft.url for ft in fetch_tasks] == ["https://techcrunch.com/article"]
    assert executor.exhausted_hosts == ["export.arxiv.org"]
