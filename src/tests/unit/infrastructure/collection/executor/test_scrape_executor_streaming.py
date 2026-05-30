"""
FR-014: ScrapeExecutor.run_streaming() runs discover and fetch concurrently.
Discover workers produce FetchTasks; fetch workers consume them and call on_result.
"""
from unittest.mock import MagicMock

from src.infrastructure.collection.executor.discover_task import DiscoverTask
from src.infrastructure.collection.executor.scrape_executor import ScrapeExecutor
from src.modules.collection.domain.entities import ScrapeJob
from src.modules.collection.domain.value_objects import ScrapedArticle


def _make_discover_task(source: str, host: str, articles: list) -> DiscoverTask:
    jobs = [ScrapeJob(url=a.url, source=source, source_type="rss") for a in articles]
    scraper = MagicMock()
    scraper.discover.return_value = jobs
    scraper.fetch.side_effect = articles
    setting = MagicMock()
    setting.source = source
    return DiscoverTask(setting=setting, scraper=scraper, host=host)


def test_run_streaming_discovers_and_fetches_all_articles():
    """FR-014: run_streaming produces one result per article across two sources."""
    articles_a = [
        ScrapedArticle(url="https://feed-a.com/1", title="A1", content="C", source="feed-a"),
        ScrapedArticle(url="https://feed-a.com/2", title="A2", content="C", source="feed-a"),
    ]
    articles_b = [
        ScrapedArticle(url="https://feed-b.com/1", title="B1", content="C", source="feed-b"),
    ]

    task_a = _make_discover_task("feed-a", "feed-a.com", articles_a)
    task_b = _make_discover_task("feed-b", "feed-b.com", articles_b)

    collected = []
    executor = ScrapeExecutor(num_workers=2, discover_workers=1, fetch_delay=0.0)
    total = executor.run_streaming([task_a, task_b], on_result=collected.append)

    assert total == 3
    assert len(collected) == 3
    urls = {a.url for a in collected}
    assert urls == {
        "https://feed-a.com/1",
        "https://feed-a.com/2",
        "https://feed-b.com/1",
    }


def test_run_streaming_calls_on_result_for_each_fetched_article():
    """FR-014: on_result callback is invoked once per successfully fetched article."""
    article = ScrapedArticle(url="https://src.com/1", title="T", content="C", source="src")
    task = _make_discover_task("src", "src.com", [article])

    on_result = MagicMock()
    executor = ScrapeExecutor(num_workers=1, discover_workers=1, fetch_delay=0.0)
    executor.run_streaming([task], on_result=on_result)

    on_result.assert_called_once()
    call_arg = on_result.call_args[0][0]
    assert call_arg.url == article.url


def test_run_streaming_returns_zero_when_no_discover_tasks():
    """FR-014: empty discover list → 0 results, no error."""
    executor = ScrapeExecutor(num_workers=1, discover_workers=1, fetch_delay=0.0)
    total = executor.run_streaming([], on_result=lambda _: None)
    assert total == 0


def test_run_streaming_applies_pre_fetch_filter():
    """FR-014: optional pre_fetch_filter is applied before fetch tasks enter the queue."""
    articles = [
        ScrapedArticle(url="https://src.com/keep", title="Keep", content="C", source="src"),
        ScrapedArticle(url="https://src.com/drop", title="Drop", content="C", source="src"),
    ]
    task = _make_discover_task("src", "src.com", articles)

    collected = []
    executor = ScrapeExecutor(num_workers=1, discover_workers=1, fetch_delay=0.0)
    executor.run_streaming(
        [task],
        on_result=collected.append,
        pre_fetch_filter=lambda tasks: [t for t in tasks if "keep" in t.url],
    )

    assert len(collected) == 1
    assert collected[0].url == "https://src.com/keep"
