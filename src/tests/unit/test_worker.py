import threading
from unittest.mock import MagicMock


def _make_fetch_task(url="http://example.com/a", result=None):
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.entities import ScrapeJob
    job = ScrapeJob(url=url, source="test", source_type="rss")
    scraper = MagicMock()
    scraper.fetch.return_value = result
    return FetchTask(url=url, source="test", job=job, scraper=scraper)


def test_executor_delivers_all_results():
    from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor
    from src.modules.collection.application.events import ArticleScrapedEvent

    events = [
        ArticleScrapedEvent(url=f"http://example.com/{i}", title=f"T{i}",
                            content="C", source="test")
        for i in range(3)
    ]
    tasks = [_make_fetch_task(url=ev.url, result=ev) for ev in events]

    collected = []
    executor = ScrapeExecutor(num_workers=2)
    executor.route(tasks)
    executor.execute(on_result=collected.append)

    assert len(collected) == 3


def test_executor_skips_none_results():
    from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor

    tasks = [
        _make_fetch_task(url="http://example.com/a", result=None),
        _make_fetch_task(url="http://example.com/b", result=None),
    ]
    collected = []
    executor = ScrapeExecutor(num_workers=1)
    executor.route(tasks)
    executor.execute(on_result=collected.append)
    assert collected == []


def test_executor_respects_per_host_exclusion():
    """Two tasks for the same host should not run concurrently."""
    import time
    from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor
    from src.modules.collection.application.events import ArticleScrapedEvent

    concurrent_count = [0]
    max_concurrent = [0]
    lock = threading.Lock()

    def slow_fetch(job):
        with lock:
            concurrent_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
        time.sleep(0.05)
        with lock:
            concurrent_count[0] -= 1
        return ArticleScrapedEvent(url=job.url, title="T", content="C", source="test")

    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.entities import ScrapeJob
    tasks = []
    for i in range(4):
        job = ScrapeJob(url=f"http://same-host.com/{i}", source="test", source_type="rss")
        scraper = MagicMock()
        scraper.fetch.side_effect = slow_fetch
        tasks.append(FetchTask(url=f"http://same-host.com/{i}", source="test",
                               job=job, scraper=scraper))

    collected = []
    executor = ScrapeExecutor(num_workers=4)
    executor.route(tasks)
    executor.execute(on_result=collected.append)

    assert max_concurrent[0] == 1  # same host: only 1 at a time
    assert len(collected) == 4