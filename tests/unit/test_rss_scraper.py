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
def test_discover_returns_keyword_matched_tasks_only():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", body=RSS_DT, status=200)
    tasks = RssScraper(url="https://example.com/feed", source="test").discover()
    assert len(tasks) == 1
    assert "dt-article" in tasks[0].url


@responses.activate
def test_discover_returns_empty_on_http_error():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed", status=500)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_network_exception():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body=Exception("Network error"))
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_discover_returns_empty_on_empty_feed():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    responses.add(responses.GET, "https://example.com/feed",
                  body='<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>',
                  status=200)
    assert RssScraper(url="https://example.com/feed", source="test").discover() == []


@responses.activate
def test_execute_returns_article_with_all_fields():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    rss = '''<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Digital Twin Innovation</title>
        <link>https://example.com/article</link>
        <description>Content about digital twins</description>
        <pubDate>Tue, 15 Jan 2024 10:00:00 GMT</pubDate>
        <author>John Doe</author>
      </item>
    </channel></rss>'''
    article_html = '<html><article><p>Full article about digital twins.</p></article></html>'
    responses.add(responses.GET, "https://example.com/feed", body=rss, status=200)
    responses.add(responses.GET, "https://example.com/article",
                  body=article_html, status=200)

    scraper = RssScraper(url="https://example.com/feed", source="techcrunch")
    article = scraper.discover()[0].execute()
    assert article.title == "Digital Twin Innovation"
    assert article.url == "https://example.com/article"
    assert article.source == "techcrunch"


# ── keyword matching (unchanged behaviour) ────────────────────────────────

def test_matches_digital_twins_variants():
    from src.ingestion.scrapers.rss_scraper import RssScraper
    s = RssScraper(url="https://example.com/feed", source="test")
    assert s._matches_keywords("Digital Twins in Manufacturing") is True
    assert s._matches_keywords("digital twin technology") is True
    assert s._matches_keywords("cyber-physical systems") is True
    assert s._matches_keywords("cyberphysical integration") is True
    assert s._matches_keywords("DIGITAL TWINS") is True
    assert s._matches_keywords("Unrelated article about cats") is False
    assert s._matches_keywords("") is False