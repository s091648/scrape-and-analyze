import pytest


def test_base_scraper_is_abstract():
    """BaseScraper should be abstract and cannot be instantiated"""
    from src.infrastructure.collection.scrapers import BaseScraper

    with pytest.raises(TypeError):
        BaseScraper()


def test_base_scraper_requires_scrape_method():
    """Subclass must implement scrape() method"""
    from src.infrastructure.collection.scrapers import BaseScraper

    class IncompleteScraper(BaseScraper):
        pass

    with pytest.raises(TypeError):
        IncompleteScraper()


def test_scraped_article_dataclass_has_fields():
    """ScrapedArticle should have required fields"""
    from src.modules.collection.application.events import ArticleScrapedEvent

    article = ArticleScrapedEvent(
        url="https://example.com",
        title="Test",
        content="Content",
        published_at="2024-01-01",
        source="test",
        topic_id=None,
        metadata={"key": "value"},
    )

    assert article.url == "https://example.com"
    assert article.title == "Test"
    assert article.source == "test"
