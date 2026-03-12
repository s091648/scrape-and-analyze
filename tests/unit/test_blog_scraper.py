import pytest
import responses
from urllib.robotparser import RobotFileParser


def test_blog_scraper_extracts_article_links():
    """BlogScraper should extract article links from listing page"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <article>
          <a href="/blog/digital-twins-article">Article 1</a>
        </article>
        <article>
          <a href="/blog/another-article">Article 2</a>
        </article>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'article a', 'title': 'h1', 'content': '.content'}
    )

    links = scraper._extract_links(html)
    assert len(links) == 2
    assert "/blog/digital-twins-article" in links[0]


def test_blog_scraper_extracts_content():
    """BlogScraper should extract title and content with selectors"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <h1>Article Title</h1>
        <div class="content">
          <p>This is the article content about digital twins.</p>
        </div>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    title, content = scraper._extract_article(html)
    assert title == "Article Title"
    assert "digital twins" in content


@responses.activate
def test_blog_scraper_checks_robots_txt():
    """BlogScraper should check robots.txt before scraping"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    robots_content = """
    User-agent: *
    Disallow: /private/
    Allow: /blog/
    """

    responses.add(
        responses.GET,
        "https://example.com/robots.txt",
        body=robots_content,
        status=200
    )

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    assert scraper._can_fetch("https://example.com/blog/article") is True
    assert scraper._can_fetch("https://example.com/private/data") is False


@responses.activate
def test_blog_scraper_handles_missing_robots_txt():
    """BlogScraper should allow scraping when robots.txt is missing"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    responses.add(
        responses.GET,
        "https://example.com/robots.txt",
        status=404
    )

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    # Should allow scraping when robots.txt is missing
    assert scraper._can_fetch("https://example.com/blog/article") is True


def test_blog_scraper_removes_nav_footer_from_content():
    """BlogScraper should exclude nav and footer from extracted content"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <nav>Navigation Menu</nav>
        <article>
          <h1>Article Title</h1>
          <div class="content">
            <p>Main content about digital twins.</p>
          </div>
        </article>
        <footer>Copyright 2024</footer>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    title, content = scraper._extract_article(html)
    assert "Navigation" not in content
    assert "Copyright" not in content
    assert "digital twins" in content


def test_blog_scraper_handles_missing_content():
    """BlogScraper should handle pages with missing content selector"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <h1>Title Only</h1>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.nonexistent'}
    )

    title, content = scraper._extract_article(html)
    assert title == "Title Only"
    assert content == ""


def test_blog_scraper_converts_relative_links():
    """BlogScraper should convert relative links to absolute URLs"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    html = '''
    <html>
      <body>
        <a href="/blog/article-1">Article 1</a>
        <a href="article-2">Article 2</a>
        <a href="https://other.com/article">External</a>
      </body>
    </html>
    '''

    scraper = BlogScraper(
        base_url="https://example.com/blog",
        source="test",
        selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'}
    )

    links = scraper._extract_links(html)
    assert "https://example.com/blog/article-1" in links
    assert "https://example.com/blog/article-2" in links
    assert "https://other.com/article" in links


@responses.activate
def test_blog_scraper_respects_rate_limit():
    """BlogScraper should wait between requests"""
    from src.scrapers.scrapers.blog_scraper import BlogScraper
    from unittest.mock import patch
    import time

    listing_html = '<html><a href="/article">Link</a></html>'
    article_html = '<html><h1>Digital Twin</h1><div class="content">Content</div></html>'

    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/article", body=article_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)

    with patch('time.sleep') as mock_sleep:
        scraper = BlogScraper(
            base_url="https://example.com/blog",
            source="test",
            selectors={'article_link': 'a', 'title': 'h1', 'content': '.content'},
            rate_limit=2.0
        )
        scraper.scrape()

        # Should have called sleep with rate_limit value
        mock_sleep.assert_called_with(2.0)

@responses.activate
def test_discover_returns_tasks_for_allowed_links():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><article><a href="/blog/dt-article">DT</a></article></body></html>'
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "article a", "title": "h1", "content": ".content"},
    )
    tasks = scraper.discover()
    assert len(tasks) == 1
    assert "dt-article" in tasks[0].url


@responses.activate
def test_discover_returns_empty_when_listing_fetch_fails():
    from src.scrapers.scrapers.blog_scraper import BlogScraper
    responses.add(responses.GET, "https://example.com/blog", status=500)
    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    assert scraper.discover() == []


@responses.activate
def test_execute_fetches_and_returns_matching_article():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><a href="/digital-twins">DT Link</a></body></html>'
    article_html = (
        '<html><body>'
        '<h1>Digital Twin Guide</h1>'
        '<div class="content"><p>Digital twins are virtual replicas.</p></div>'
        '</body></html>'
    )
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)
    responses.add(responses.GET, "https://example.com/digital-twins",
                  body=article_html, status=200)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    article = scraper.discover()[0].execute()
    assert article is not None
    assert article.title == "Digital Twin Guide"
    assert article.source == "test"


@responses.activate
def test_execute_returns_none_for_non_keyword_article():
    from src.scrapers.scrapers.blog_scraper import BlogScraper

    listing_html = '<html><body><a href="/unrelated">No DT here</a></body></html>'
    article_html = '<html><body><h1>Cloud News</h1><div class="content"><p>About AWS.</p></div></body></html>'
    responses.add(responses.GET, "https://example.com/blog", body=listing_html, status=200)
    responses.add(responses.GET, "https://example.com/robots.txt", status=404)
    responses.add(responses.GET, "https://example.com/unrelated",
                  body=article_html, status=200)

    scraper = BlogScraper(
        base_url="https://example.com/blog", source="test",
        selectors={"article_link": "a", "title": "h1", "content": ".content"},
    )
    tasks = scraper.discover()
    assert tasks[0].execute() is None