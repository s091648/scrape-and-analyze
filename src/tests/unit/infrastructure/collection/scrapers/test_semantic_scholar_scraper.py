from unittest.mock import MagicMock, patch, Mock
from src.infrastructure.collection.clients.semantic_scholar_client import (
    SemanticScholarEntry,
    SemanticScholarRateLimitedError,
)
from src.modules.collection.domain.entities import ScrapeJob


def _make_entry(
    paper_id="abc123",
    arxiv_id="2501.12345",
    title="Test Paper",
    abstract="An abstract.",
    pdf_url="https://example.com/paper.pdf",
    citation_count=10,
    is_open_access=True,
):
    url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else f"https://www.semanticscholar.org/paper/{paper_id}"
    return SemanticScholarEntry(
        paper_id=paper_id,
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
        source="semantic_scholar",
        source_type="semantic_scholar",
        metadata={
            "paper_id": "abc123",
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
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = [
        _make_entry(paper_id="p1", arxiv_id="2501.00001", title="Paper One"),
        _make_entry(paper_id="p2", arxiv_id="2501.00002", title="Paper Two"),
    ]

    scraper = SemanticScholarScraper(
        keywords=["digital twin", "neural rendering"],
        client=mock_client,
        fetch_pdf=False,
    )
    jobs = scraper.discover()

    assert len(jobs) == 2
    assert all(j.source == "semantic_scholar" for j in jobs)
    assert all(j.source_type == "semantic_scholar" for j in jobs)
    assert jobs[0].metadata["title"] == "Paper One"
    assert jobs[1].metadata["title"] == "Paper Two"
    mock_client.fetch_papers.assert_called_once()


def test_discover_no_keywords_returns_empty():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    mock_client = MagicMock()
    scraper = SemanticScholarScraper(keywords=None, client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert jobs == []
    mock_client.fetch_papers.assert_not_called()


def test_discover_rate_limited_returns_empty():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.side_effect = SemanticScholarRateLimitedError("429")

    scraper = SemanticScholarScraper(
        keywords=["digital twin"],
        client=mock_client,
        fetch_pdf=False,
    )
    jobs = scraper.discover()

    assert jobs == []


def test_discover_arxiv_url_in_scrape_job():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    mock_client = MagicMock()
    mock_client.fetch_papers.return_value = [
        _make_entry(paper_id="p1", arxiv_id="2501.99999"),
    ]

    scraper = SemanticScholarScraper(keywords=["test"], client=mock_client, fetch_pdf=False)
    jobs = scraper.discover()

    assert len(jobs) == 1
    assert jobs[0].url == "https://arxiv.org/abs/2501.99999"
    assert jobs[0].metadata["arxiv_id"] == "2501.99999"


# ── fetch() tests ─────────────────────────────────────────────────────────────

def test_fetch_no_pdf_returns_abstract():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    job = _make_job(pdf_url=None)
    scraper = SemanticScholarScraper(keywords=["test"], fetch_pdf=False)
    article = scraper.fetch(job)

    assert article is not None
    assert article.extra["pdf_available"] is False
    assert article.extra["sections"] == {}
    assert article.content == "An abstract."
    assert article.source == "semantic_scholar"


def test_fetch_with_pdf_parses_sections():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    job = _make_job(pdf_url="https://example.com/paper.pdf")

    with patch(
        "src.infrastructure.collection.scrapers.semantic_scholar_scraper.PdfParser"
    ) as MockPdfParser:
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.return_value = "Full PDF text."
        mock_parser_instance.extract_sections.return_value = {
            "introduction": "Intro text.",
            "conclusion": "Conclusion.",
        }
        MockPdfParser.return_value = mock_parser_instance

        scraper = SemanticScholarScraper(keywords=["test"], fetch_pdf=True)
        article = scraper.fetch(job)

    assert article.extra["pdf_available"] is True
    assert article.extra["sections"] == {
        "introduction": "Intro text.",
        "conclusion": "Conclusion.",
    }


def test_fetch_pdf_parse_failure_returns_abstract():
    from src.infrastructure.collection.scrapers.semantic_scholar_scraper import SemanticScholarScraper

    job = _make_job(pdf_url="https://example.com/paper.pdf")

    with patch(
        "src.infrastructure.collection.scrapers.semantic_scholar_scraper.PdfParser"
    ) as MockPdfParser:
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse.return_value = None
        MockPdfParser.return_value = mock_parser_instance

        scraper = SemanticScholarScraper(keywords=["test"], fetch_pdf=True)
        article = scraper.fetch(job)

    assert article.extra["pdf_available"] is False
    assert article.extra["sections"] == {}
    assert article.content == "An abstract."
