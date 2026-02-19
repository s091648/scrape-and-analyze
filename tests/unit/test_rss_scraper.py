import pytest
import responses


@responses.activate
def test_rss_scraper_parses_feed():
    """RssScraper should parse RSS feed entries"""
    from src.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Digital Twins in Manufacturing</title>
          <link>https://example.com/digital-twins-article</link>
          <description>An article about digital twins technology.</description>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Unrelated Article</title>
          <link>https://example.com/unrelated</link>
          <description>Nothing about our topic.</description>
          <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>'''

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=rss_content,
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    # Should only get the digital twins article (keyword filtered)
    assert len(articles) == 1
    assert "Digital Twins" in articles[0].title


def test_rss_scraper_matches_keywords():
    """RssScraper should match Digital Twins keywords"""
    from src.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("Digital Twins in Manufacturing") is True
    assert scraper._matches_keywords("The rise of digital twin technology") is True
    assert scraper._matches_keywords("IoT and digital twins") is True
    assert scraper._matches_keywords("Unrelated article about cats") is False


@responses.activate
def test_rss_scraper_handles_network_error():
    """RssScraper should handle network errors gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=Exception("Network error")
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []


@responses.activate
def test_rss_scraper_handles_500_error():
    """RssScraper should handle HTTP 500 errors gracefully"""
    from src.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        status=500
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []
