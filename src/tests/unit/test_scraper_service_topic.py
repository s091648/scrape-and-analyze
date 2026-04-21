from unittest.mock import MagicMock


def test_scraper_service_passes_topic_id_to_rss_scraper():
    from src.ingestion.services.scraper_service import ScraperService
    from src.pipeline.dispatcher import ScrapeDispatcher

    dispatcher = MagicMock(spec=ScrapeDispatcher)
    dispatcher.run = MagicMock()
    svc = ScraperService(dispatcher=dispatcher)

    sources = [{
        "id": "abc",
        "source": "test-rss",
        "url": "https://example.com/feed",
        "source_type": "rss",
        "selector_config": {"keywords": [r"3d\s+ai"]},
        "topic_id": "topic-uuid-123",
        "prompt_override": None,
    }]

    # Build scraper directly and inspect its attributes
    scraper = svc._build_scraper(sources[0])
    assert scraper._topic_id == "topic-uuid-123"
    assert scraper._keyword_pattern is not None
