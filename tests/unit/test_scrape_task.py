def test_execute_calls_fn_and_returns_result():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    from src.scrapers.scrapers.article import ScrapedArticle
    article = ScrapedArticle(url="http://x.com", title="T", content="C",
                             published_at=None, source="test")
    task = ScrapeTask(url="http://x.com", source="test", _execute_fn=lambda: article)
    assert task.execute() is article


def test_execute_returns_none_on_exception():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    task = ScrapeTask(url="http://x.com", source="test",
                      _execute_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert task.execute() is None


def test_task_has_url_and_source():
    from src.scrapers.strategy.scrape_task import ScrapeTask
    task = ScrapeTask(url="http://a.com/p", source="blog", _execute_fn=lambda: None)
    assert task.url == "http://a.com/p"
    assert task.source == "blog"
    assert task.metadata == {}