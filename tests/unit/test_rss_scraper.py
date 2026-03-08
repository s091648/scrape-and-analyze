import pytest
import responses


@responses.activate
def test_rss_scraper_parses_feed():
    """RssScraper should parse RSS feed entries"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

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
    from src.scrapers.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("Digital Twins in Manufacturing") is True
    assert scraper._matches_keywords("The rise of digital twin technology") is True
    assert scraper._matches_keywords("IoT and digital twins") is True
    assert scraper._matches_keywords("Unrelated article about cats") is False


@responses.activate
def test_rss_scraper_handles_network_error():
    """RssScraper should handle network errors gracefully"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

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
    from src.scrapers.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        status=500
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []


@responses.activate
def test_rss_scraper_handles_malformed_xml():
    """RssScraper should handle malformed XML gracefully"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body="<not valid xml",
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="test")
    articles = scraper.scrape()

    assert articles == []


@responses.activate
def test_rss_scraper_handles_empty_feed():
    """RssScraper should handle empty feed"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Empty Feed</title>
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

    assert articles == []


@responses.activate
def test_rss_scraper_extracts_all_fields():
    """RssScraper should extract title, link, description, pubDate"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    rss_content = '''<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Digital Twin Innovation</title>
          <link>https://example.com/article</link>
          <description>Content about digital twins</description>
          <pubDate>Tue, 15 Jan 2024 10:00:00 GMT</pubDate>
          <author>John Doe</author>
        </item>
      </channel>
    </rss>'''

    responses.add(
        responses.GET,
        "https://example.com/feed",
        body=rss_content,
        status=200
    )

    scraper = RssScraper(url="https://example.com/feed", source="techcrunch")
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Digital Twin Innovation"
    assert articles[0].url == "https://example.com/article"
    assert articles[0].source == "techcrunch"
    assert "digital twins" in articles[0].content.lower()


def test_keyword_matching_case_insensitive():
    """Keyword matching should be case insensitive"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("DIGITAL TWINS") is True
    assert scraper._matches_keywords("Digital Twins") is True
    assert scraper._matches_keywords("digital twins") is True


def test_keyword_matching_partial_match():
    """Keyword matching should work with surrounding text"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("The future of digital twins in industry") is True
    assert scraper._matches_keywords("How digital twin technology is evolving") is True


def test_keyword_matching_rejects_unrelated():
    """Keyword matching should reject unrelated content"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("AI and machine learning trends") is False
    assert scraper._matches_keywords("Cloud computing news") is False
    assert scraper._matches_keywords("") is False


def test_keyword_matching_cyber_physical():
    """Keyword matching should match cyber-physical variants"""
    from src.scrapers.scrapers.rss_scraper import RssScraper

    scraper = RssScraper(url="https://example.com/feed", source="test")

    assert scraper._matches_keywords("cyber-physical systems") is True
    assert scraper._matches_keywords("cyberphysical integration") is True
