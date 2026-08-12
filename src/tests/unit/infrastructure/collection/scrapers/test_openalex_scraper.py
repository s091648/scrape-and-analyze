import pytest
from unittest.mock import MagicMock, patch
from src.infrastructure.collection.clients.openalex_client import (
    OpenAlexEntry,
    OpenAlexRateLimitedError,
)
from src.modules.collection.domain.entities import ScrapeJob


def _make_entry(
    work_id="https://openalex.org/W123456",
    arxiv_id="2501.12345",
    title="Test Paper",
    abstract="An abstract.",
    pdf_url="https://example.com/paper.pdf",
    citation_count=10,
    is_open_access=True,
):
    if arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    else:
        url = work_id
    return OpenAlexEntry(
        work_id=work_id,
        url=url,
        title=title,
        abstract=abstract,
        authors=["Author One"],
        publication_date="2025-01-15",
        open_access_pdf_url=pdf_url,
        doi="10.1234/test",
        arxiv_id=arxiv_id,
        citation_count=citation_count,
        is_open_access=is_open_access,
    )


def _make_job(
    url="https://arxiv.org/abs/2501.12345",
    title="Test Paper",
    abstract="An abstract.",
    pdf_url="https://example.com/paper.pdf",
    arxiv_id="2501.12345",
):
    return ScrapeJob(
        url=url,
        source="openalex",
        source_type="openalex",
        metadata={
            "work_id": "https://openalex.org/W123456",
            "title": title,
            "abstract": abstract,
            "open_access_pdf_url": pdf_url,
            "doi": "10.1234/test",
            "arxiv_id": arxiv_id,
            "citation_count": 10,
            "is_open_access": True,
            "authors": ["Author One"],
            "published": "2025-01-15",
        },
    )


# ── discover() tests ──────────────────────────────────────────────────────────

def test_discover_with_keywords():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = [
        _make_entry(work_id="https://openalex.org/W1", arxiv_id="2501.00001", title="Paper One"),
        _make_entry(work_id="https://openalex.org/W2", arxiv_id="2501.00002", title="Paper Two"),
    ]

    scraper = OpenAlexScraper(keywords=["digital twin", "neural rendering"], client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert len(jobs) == 2
    assert all(j.source == "openalex" for j in jobs)
    assert all(j.source_type == "openalex" for j in jobs)
    assert jobs[0].metadata["title"] == "Paper One"
    assert jobs[1].metadata["title"] == "Paper Two"
    mock_client.fetch_papers.assert_called_once()


def test_discover_no_keywords_returns_empty():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    scraper = OpenAlexScraper(keywords=None, client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert jobs == []
    mock_client.fetch_papers.assert_not_called()


def test_discover_rate_limited_reraises():
    """discover() must re-raise OpenAlexRateLimitedError (not swallow it) so
    ScrapeExecutor can abort remaining same-host discovers for this run —
    matches ArxivScraper's existing behavior (see rate_limit_errors.py)."""
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.side_effect = OpenAlexRateLimitedError("429")

    scraper = OpenAlexScraper(keywords=["digital twin"], client=mock_client, fetch_pdf=False)
    with pytest.raises(OpenAlexRateLimitedError):
        scraper.discover()


def test_discover_keywords_joined_as_query():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = []

    scraper = OpenAlexScraper(keywords=["digital twin", "iot"], client=mock_client, fetch_pdf=False)
    scraper.discover()

    call_kwargs = mock_client.fetch_papers.call_args
    query = call_kwargs.kwargs.get("query") or call_kwargs[0][0]
    assert query == "digital twin iot"


def test_discover_arxiv_url_in_scrape_job():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = [
        _make_entry(arxiv_id="2501.99999"),
    ]

    scraper = OpenAlexScraper(keywords=["test"], client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert len(jobs) == 1
    assert jobs[0].url == "https://arxiv.org/abs/2501.99999"
    assert jobs[0].metadata["arxiv_id"] == "2501.99999"


def test_discover_work_id_stored_in_metadata():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = [
        _make_entry(work_id="https://openalex.org/W999"),
    ]

    scraper = OpenAlexScraper(keywords=["test"], client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert jobs[0].metadata["work_id"] == "https://openalex.org/W999"


# ── fetch() tests ─────────────────────────────────────────────────────────────

def test_fetch_no_pdf_returns_abstract():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    job = _make_job(pdf_url=None)
    scraper = OpenAlexScraper(keywords=["test"], fetch_pdf=False)
    article = scraper.fetch(job)

    assert article is not None
    assert article.extra["pdf_available"] is False
    assert article.extra["sections"] == {}
    assert article.content == "An abstract."
    assert article.source == "openalex"


def test_fetch_with_pdf_parses_sections():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    job = _make_job(pdf_url="https://example.com/paper.pdf")

    with patch("src.infrastructure.collection.scrapers.openalex_scraper.PdfParser") as MockPdfParser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = "Full PDF text."
        mock_parser.extract_sections.return_value = {
            "introduction": "Intro text.",
            "conclusion": "Conclusion.",
        }
        MockPdfParser.return_value = mock_parser

        scraper = OpenAlexScraper(keywords=["test"], fetch_pdf=True)
        article = scraper.fetch(job)

    assert article.extra["pdf_available"] is True
    assert article.extra["sections"] == {
        "introduction": "Intro text.",
        "conclusion": "Conclusion.",
    }


def test_fetch_pdf_parse_failure_falls_back_to_abstract():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    job = _make_job(pdf_url="https://example.com/paper.pdf")

    with patch("src.infrastructure.collection.scrapers.openalex_scraper.PdfParser") as MockPdfParser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = None
        MockPdfParser.return_value = mock_parser

        scraper = OpenAlexScraper(keywords=["test"], fetch_pdf=True)
        article = scraper.fetch(job)

    assert article.extra["pdf_available"] is False
    assert article.extra["sections"] == {}
    assert article.content == "An abstract."


def test_fetch_title_fallback_to_work_id():
    from src.infrastructure.collection.scrapers.openalex_scraper import OpenAlexScraper

    job = ScrapeJob(
        url="https://openalex.org/W000",
        source="openalex",
        source_type="openalex",
        metadata={
            "work_id": "https://openalex.org/W000",
            "title": None,
            "abstract": "",
            "open_access_pdf_url": None,
            "doi": None,
            "arxiv_id": None,
            "citation_count": 0,
            "is_open_access": False,
            "authors": [],
            "published": None,
        },
    )
    scraper = OpenAlexScraper(keywords=["test"], fetch_pdf=False)
    article = scraper.fetch(job)

    assert article.title == "https://openalex.org/W000"
