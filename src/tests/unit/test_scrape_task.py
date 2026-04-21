from unittest.mock import MagicMock


def _make_fetch_task(execute_result=None):
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.value_objects import ScrapeJob
    job = ScrapeJob(url="http://x.com", source="test", source_type="rss")
    scraper = MagicMock()
    scraper.fetch.return_value = execute_result
    return FetchTask(url="http://x.com", source="test", job=job, scraper=scraper)


def test_execute_calls_scraper_fetch_and_returns_result():
    from src.modules.collection.application.events import ArticleScrapedEvent
    event = ArticleScrapedEvent(url="http://x.com", title="T", content="C", source="test")
    task = _make_fetch_task(execute_result=event)
    assert task.execute() is event


def test_execute_returns_none_on_exception():
    from src.infrastructure.collection.executor.fetch_task import FetchTask
    from src.modules.collection.domain.value_objects import ScrapeJob
    job = ScrapeJob(url="http://x.com", source="test", source_type="rss")
    scraper = MagicMock()
    scraper.fetch.side_effect = RuntimeError("boom")
    task = FetchTask(url="http://x.com", source="test", job=job, scraper=scraper)
    assert task.execute() is None


def test_task_has_url_and_source():
    task = _make_fetch_task()
    assert task.url == "http://x.com"
    assert task.source == "test"
    assert task.metadata == {}