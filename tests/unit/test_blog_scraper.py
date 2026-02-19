import pytest
import responses
from urllib.robotparser import RobotFileParser


def test_blog_scraper_extracts_article_links():
    """BlogScraper should extract article links from listing page"""
    from src.scrapers.blog_scraper import BlogScraper

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
    from src.scrapers.blog_scraper import BlogScraper

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
    from src.scrapers.blog_scraper import BlogScraper

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
    from src.scrapers.blog_scraper import BlogScraper

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
