import responses

RSS_DT = '''<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Digital Twins in Manufacturing</title>
    <link>https://example.com/dt-article</link>
    <description>An article about digital twins technology.</description>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Unrelated Article</title>
    <link>https://example.com/unrelated</link>
    <description>Nothing here.</description>
  </item>
</channel></rss>'''


@responses.activate
def test_discover_returns_keyword_matched_jobs_only():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", body=RSS_DT, status=200)
    jobs = RssScraper(url="https://example.com/feed", source="test").discover()
    assert len(jobs) == 1
    assert "dt-article" in jobs[0].url


@responses.activate
def test_discover_returns_empty_on_http_error():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", status=500)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_network_exception():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body=Exception("Network error"))
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_empty_feed():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body='<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
                  status=200)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_fetch_returns_event_with_all_fields():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    rss = '''<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Digital Twin Innovation</title>
        <link>https://example.com/article</link>
        <description>Content about digital twins</description>
        <pubDate>Tue, 15 Jan 2024 10:00:00 GMT</pubDate>
      </item>
    </channel></rss>'''
    article_html = '<html><article><p>Full article about digital twins.</p></article></html>'
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)
    responses.add(responses.GET, "https://example.com/article",
                  body=article_html, status=200)

    scraper = RssScraper(url="https://example.com/feed", source="techcrunch")
    jobs = scraper.discover()
    event = scraper.fetch(jobs[0])
    assert event.title == "Digital Twin Innovation"
    assert event.url == "https://example.com/article"
    assert event.source == "techcrunch"


@responses.activate
def test_discover_matches_on_description_when_title_misses():
    """FR-003: keyword match checks both title AND description."""
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    rss = '''<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Unrelated Title</title>
    <link>https://example.com/dt-desc</link>
    <description>An article about digital twins technology.</description>
  </item>
  <item>
    <title>No match here</title>
    <link>https://example.com/nomatch</link>
    <description>Completely unrelated content.</description>
  </item>
</channel></rss>'''
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)
    jobs = RssScraper(url="https://example.com/feed", source="test").discover()
    assert len(jobs) == 1
    assert "dt-desc" in jobs[0].url


@responses.activate
def test_discover_accepts_all_when_keywords_empty_list():
    """FR-003: keywords=[] disables filtering — all articles are accepted."""
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    rss = '''<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Completely Unrelated Article</title>
    <link>https://example.com/a</link>
    <description>Nothing to do with digital twins.</description>
  </item>
  <item>
    <title>Another Unrelated Article</title>
    <link>https://example.com/b</link>
    <description>Still nothing relevant.</description>
  </item>
</channel></rss>'''
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)
    jobs = RssScraper(url="https://example.com/feed", source="test", keywords=[]).discover()
    assert len(jobs) == 2  # all entries accepted, no keyword filter


def test_matches_digital_twins_variants():
    from src.infrastructure.collection.scrapers.rss_scraper import RssScraper
    s = RssScraper(url="https://example.com/feed", source="test")
    assert s._matches("Digital Twins in Manufacturing") is True
    assert s._matches("digital twin technology") is True
    assert s._matches("cyber-physical systems") is True
    assert s._matches("cyberphysical integration") is True
    assert s._matches("DIGITAL TWINS") is True
    assert s._matches("Unrelated article about cats") is False
    assert s._matches("") is False