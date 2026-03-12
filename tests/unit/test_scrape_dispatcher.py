from unittest.mock import patch


def _make_scraper(articles):
    from src.scrapers.scrapers.base_scraper import BaseScraper
    from src.scrapers.strategy.scrape_task import ScrapeTask

    class FakeScraper(BaseScraper):
        def discover(self):
            return [
                ScrapeTask(url=f"http://example.com/{i}", source="test",
                           _execute_fn=lambda a=a: a)
                for i, a in enumerate(articles)
            ]
    return FakeScraper()


def _make_articles(n):
    from src.scrapers.scrapers.article import ScrapedArticle
    return [
        ScrapedArticle(url=f"http://example.com/{i}", title=f"T{i}",
                       content="C", published_at=None, source="test")
        for i in range(n)
    ]


def test_dispatcher_delivers_all_results():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    articles = _make_articles(3)
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=2, delay=0.0).run(
            [_make_scraper(articles)], on_result=results.append
        )
    assert len(results) == 3


def test_dispatcher_handles_empty_scraper():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=1, delay=0.0).run(
            [_make_scraper([])], on_result=results.append
        )
    assert results == []


def test_dispatcher_accepts_custom_selector():
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher
    from src.scrapers.strategy.queue_selector import RoundRobinQueueSelector
    articles = _make_articles(2)
    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(
            num_workers=1, delay=0.0,
            selector=RoundRobinQueueSelector(),
        ).run([_make_scraper(articles)], on_result=results.append)
    assert len(results) == 2


def test_dispatcher_handles_discover_exception_gracefully():
    from src.scrapers.scrapers.base_scraper import BaseScraper
    from src.scrapers.strategy.scrape_dispatcher import ScrapeDispatcher

    class BrokenScraper(BaseScraper):
        def discover(self):
            raise RuntimeError("network down")

    results = []
    with patch("src.scrapers.strategy.worker.time.sleep"):
        ScrapeDispatcher(num_workers=1, delay=0.0).run(
            [BrokenScraper()], on_result=results.append
        )
    assert results == []