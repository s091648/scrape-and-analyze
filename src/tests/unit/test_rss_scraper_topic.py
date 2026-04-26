from unittest.mock import MagicMock
from src.infrastructure.collection.clients.rss_client import RssEntry


def _make_entry(title="Digital Twin article"):
    e = MagicMock(spec=RssEntry)
    e.url = "https://example.com/article"
    e.title = title
    e.description = "A description about digital twin."
    e.published = None
    e.author = None
    return e


def test_rss_scraper_uses_selector_config_keywords():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    client = MagicMock()
    client.fetch_feed.return_value = [
        _make_entry("3D AI model research"),
        _make_entry("Unrelated cooking article"),
    ]
    scraper = RssScraper(
        url="https://example.com/feed",
        source="test",
        keywords=[r"3d\s+ai", r"neural\s+render"],
        topic_id="topic-uuid-123",
        client=client,
    )
    jobs = scraper.discover()
    assert len(jobs) == 1
    assert str(jobs[0].topic_id) == "topic-uuid-123"


def test_rss_scraper_falls_back_to_hardcoded_keywords_when_none_provided():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    client = MagicMock()
    client.fetch_feed.return_value = [_make_entry("Digital twin simulation")]
    scraper = RssScraper(url="https://example.com/feed", source="test", client=client)
    jobs = scraper.discover()
    assert len(jobs) == 1