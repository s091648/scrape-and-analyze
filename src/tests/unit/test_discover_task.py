import pytest
from unittest.mock import MagicMock
from src.infrastructure.collection.executor.discover_task import DiscoverTask
from src.infrastructure.collection.executor.fetch_task import FetchTask
from src.infrastructure.collection.clients.arxiv_client import ArxivRateLimitedError
from src.modules.collection.domain.entities import ScrapeJob


def test_discover_task_execute_returns_fetch_tasks():
    job = ScrapeJob(url="http://arxiv.org/abs/1", source="arxiv", source_type="arxiv")
    scraper = MagicMock()
    scraper.discover.return_value = [job]
    setting = MagicMock()

    task = DiscoverTask(setting=setting, scraper=scraper, host="export.arxiv.org")
    results = task.execute()

    assert len(results) == 1
    assert isinstance(results[0], FetchTask)
    assert results[0].url == "http://arxiv.org/abs/1"
    assert results[0].scraper is scraper


def test_discover_task_execute_returns_empty_on_failure():
    scraper = MagicMock()
    scraper.discover.side_effect = RuntimeError("timeout")
    setting = MagicMock()

    task = DiscoverTask(setting=setting, scraper=scraper, host="export.arxiv.org")
    results = task.execute()

    assert results == []


def test_discover_task_execute_returns_empty_on_empty_discover():
    scraper = MagicMock()
    scraper.discover.return_value = []
    setting = MagicMock()

    task = DiscoverTask(setting=setting, scraper=scraper, host="export.arxiv.org")
    results = task.execute()

    assert results == []


def test_discover_task_propagates_arxiv_rate_limited_error():
    """ArxivRateLimitedError must not be silenced — the executor needs it to abort remaining tasks."""
    scraper = MagicMock()
    scraper.discover.side_effect = ArxivRateLimitedError("429 Too Many Requests")
    setting = MagicMock()

    task = DiscoverTask(setting=setting, scraper=scraper, host="export.arxiv.org")
    with pytest.raises(ArxivRateLimitedError):
        task.execute()
