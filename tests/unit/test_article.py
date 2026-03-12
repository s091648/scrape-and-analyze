def test_scraped_article_dataclass():
    from src.scrapers.scrapers.article import ScrapedArticle
    a = ScrapedArticle(url="http://x.com", title="T", content="C",
                       published_at="2024-01-01", source="test")
    assert a.url == "http://x.com"
    assert a.metadata == {}
