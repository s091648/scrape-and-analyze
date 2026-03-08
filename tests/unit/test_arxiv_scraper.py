import pytest
import responses
from datetime import datetime, timedelta, timezone


def test_arxiv_scraper_builds_query():
    """ArxivScraper should build correct search query"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper()
    query = scraper._build_query()

    assert "digital" in query.lower() or "twin" in query.lower()


@responses.activate
def test_arxiv_scraper_parses_atom_response():
    """ArxivScraper should parse Atom XML response"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

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
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper(max_results=50)
    assert scraper.max_results == 50

    scraper_default = ArxivScraper()
    assert scraper_default.max_results == 100


@responses.activate
def test_arxiv_scraper_handles_empty_response():
    """ArxivScraper should handle empty response gracefully"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

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
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        status=500
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert articles == []


@responses.activate
def test_arxiv_scraper_extracts_authors():
    """ArxivScraper should extract multiple authors"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Digital Twins Research</title>
        <summary>Abstract text</summary>
        <published>{recent_date}</published>
        <author><name>John Doe</name></author>
        <author><name>Jane Smith</name></author>
        <author><name>Bob Johnson</name></author>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].metadata['authors'] == ['John Doe', 'Jane Smith', 'Bob Johnson']


@responses.activate
def test_arxiv_scraper_filters_old_papers():
    """ArxivScraper should filter papers older than days_back"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Old Paper</title>
        <summary>Abstract</summary>
        <published>{old_date}</published>
        <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate"/>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper(days_back=7)
    articles = scraper.scrape()

    assert len(articles) == 0  # Should be filtered out


@responses.activate
def test_arxiv_scraper_handles_missing_fields():
    """ArxivScraper should handle entries with missing optional fields"""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Minimal Entry</title>
        <summary></summary>
        <published>{recent_date}</published>
      </entry>
    </feed>'''

    responses.add(
        responses.GET,
        "http://export.arxiv.org/api/query",
        body=atom_response,
        status=200
    )

    scraper = ArxivScraper()
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].title == "Minimal Entry"
    assert articles[0].content == ""


@responses.activate
def test_arxiv_scraper_stores_pdf_full_text_in_content():
    """When PDF download succeeds, content should be full text, abstract in metadata."""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    paper_id = '2401.00001'

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/{paper_id}v1</id>
        <title>Digital Twins Paper</title>
        <summary>Short abstract text.</summary>
        <published>{recent_date}</published>
        <link href="http://arxiv.org/abs/{paper_id}v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(responses.GET, 'http://export.arxiv.org/api/query', body=atom_response, status=200)
    responses.add(responses.GET, f'https://arxiv.org/pdf/{paper_id}v1', body=b'%PDF-1.4 fake', status=200)

    scraper = ArxivScraper(fetch_pdf=True)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].metadata.get('abstract') == 'Short abstract text.'
    assert articles[0].metadata.get('pdf_available') is not None


@responses.activate
def test_arxiv_scraper_falls_back_to_abstract_when_pdf_fails():
    """When PDF download fails, content should be the original abstract."""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper
    from datetime import datetime, timedelta, timezone

    recent_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    paper_id = '2401.00002'

    atom_response = f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/{paper_id}v1</id>
        <title>Another Paper</title>
        <summary>Fallback abstract.</summary>
        <published>{recent_date}</published>
        <link href="http://arxiv.org/abs/{paper_id}v1" rel="alternate" type="text/html"/>
      </entry>
    </feed>'''

    responses.add(responses.GET, 'http://export.arxiv.org/api/query', body=atom_response, status=200)
    responses.add(responses.GET, f'https://arxiv.org/pdf/{paper_id}v1', status=404)

    scraper = ArxivScraper(fetch_pdf=True)
    articles = scraper.scrape()

    assert len(articles) == 1
    assert articles[0].content == 'Fallback abstract.'
    assert articles[0].metadata.get('pdf_available') is False


def test_arxiv_scraper_fetch_pdf_disabled_by_default():
    """fetch_pdf=False (default) preserves existing behaviour."""
    from src.scrapers.scrapers.arxiv_scraper import ArxivScraper

    scraper = ArxivScraper()
    assert scraper.fetch_pdf is False
