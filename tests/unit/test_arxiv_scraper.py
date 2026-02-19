import pytest
import responses
from datetime import datetime, timedelta, timezone


def test_arxiv_scraper_builds_query():
    """ArxivScraper should build correct search query"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper()
    query = scraper._build_query()

    assert "digital" in query.lower() or "twin" in query.lower()


@responses.activate
def test_arxiv_scraper_parses_atom_response():
    """ArxivScraper should parse Atom XML response"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Digital Twins for Smart Manufacturing</title>
        <summary>This paper presents a framework for digital twins...</summary>
        <published>{recent_date}</published>
        <author><name>John Doe</name></author>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper(max_results=10)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert "Digital Twins" in articles[0].title
    assert articles[0].source == "arxiv"


def test_arxiv_scraper_respects_max_results():
    """ArxivScraper should respect max_results limit"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper(max_results=50)
    assert scraper.max_results == 50

    scraper_default = ArxivScraper()
    assert scraper_default.max_results == 100


@responses.activate
def test_arxiv_scraper_handles_empty_response():
    """ArxivScraper should handle empty response gracefully"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    atom_response = '''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert articles == []


@responses.activate
def test_arxiv_scraper_handles_api_error():
    """ArxivScraper should handle API errors gracefully"""
    from src.scrapers.arxiv_scraper import ArxivScraper

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        status=500
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert articles == []
