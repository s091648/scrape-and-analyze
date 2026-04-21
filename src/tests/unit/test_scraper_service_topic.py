def test_scraper_factory_passes_topic_id_to_rss_scraper():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.modules.collection.domain.entities import ScraperSetting
    from uuid import uuid4

    topic_id = uuid4()
    setting = ScraperSetting(
        source="test-rss",
        source_type="rss",
        url="https://example.com/feed",
        interval_hours=24,
        topic_id=topic_id,
        selector_config={"keywords": [r"3d\s+ai"]},
    )
    factory = ConcreteScraperFactory()
    scraper = factory.create_for(setting)

    assert scraper._topic_id == topic_id or getattr(scraper, "_topic_id", None) == topic_id


def test_scraper_factory_creates_arxiv_scraper_for_arxiv_source():
    from src.infrastructure.collection.scrapers.scraper_factory import ConcreteScraperFactory
    from src.infrastructure.collection.scrapers.arxiv_scraper import ArxivScraper
    from src.modules.collection.domain.entities import ScraperSetting

    setting = ScraperSetting(
        source="arxiv", source_type="arxiv",
        url="", interval_hours=6,
        selector_config={"max_results": 30, "days_back": 1},
    )
    factory = ConcreteScraperFactory()
    scraper = factory.create_for(setting)
    assert isinstance(scraper, ArxivScraper)