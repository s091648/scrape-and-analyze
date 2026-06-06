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


def test_scraped_article_dto_has_fields():
    from src.modules.collection.application.events import ArticleScrapedEvent

    dto = ArticleScrapedEvent(
        url="https://example.com",
        title="Test",
        content="Content",
        source="test",
        topic_id=None,
        metadata={"key": "value"},
    )

    assert dto.url == "https://example.com"
    assert dto.title == "Test"
    assert dto.source == "test"
