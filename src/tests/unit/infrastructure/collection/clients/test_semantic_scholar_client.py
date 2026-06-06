import pytest
from unittest.mock import MagicMock, Mock
import requests.exceptions

SAMPLE_PAPER = {
    "paperId": "abc123",
    "title": "Test Paper",
    "abstract": "A test abstract",
    "authors": [{"authorId": "1", "name": "Author One"}],
    "publicationDate": "2025-01-15",
    "year": 2025,
    "openAccessPdf": {"url": "https://example.com/paper.pdf", "status": "GREEN"},
    "externalIds": {"ArXiv": "2501.12345", "DOI": "10.1234/test"},
    "isOpenAccess": True,
    "citationCount": 42,
}

SAMPLE_PAPER_NO_ARXIV = {
    "paperId": "xyz789",
    "title": "No ArXiv Paper",
    "abstract": "Another abstract",
    "authors": [{"authorId": "2", "name": "Author Two"}],
    "publicationDate": "2025-02-01",
    "year": 2025,
    "openAccessPdf": None,
    "externalIds": {"DOI": "10.5678/other"},
    "isOpenAccess": False,
    "citationCount": 5,
}


def _make_client(response_data: dict):
    """Build a SemanticScholarClient with a mocked http_client returning response_data."""
    from src.infrastructure.collection.clients.semantic_scholar_client import SemanticScholarClient

    mock_response = MagicMock()
    mock_response.json.return_value = response_data

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response

    return SemanticScholarClient(api_key=None, http_client=mock_http), mock_http


def test_fetch_papers_returns_entries():
    from src.infrastructure.collection.clients.semantic_scholar_client import SemanticScholarClient, SemanticScholarEntry

    second_paper = dict(SAMPLE_PAPER_NO_ARXIV)
    second_paper["externalIds"] = {"DOI": "10.5678/other"}
    second_paper["openAccessPdf"] = None

    client, _ = _make_client({"data": [SAMPLE_PAPER, second_paper]})
    entries = client.fetch_papers(query="digital twin")

    assert len(entries) == 2
    assert all(isinstance(e, SemanticScholarEntry) for e in entries)
    assert entries[0].paper_id == "abc123"
    assert entries[0].title == "Test Paper"
    assert entries[0].abstract == "A test abstract"
    assert entries[0].authors == ["Author One"]
    assert entries[0].citation_count == 42
    assert entries[0].is_open_access is True


def test_fetch_papers_arxiv_url_normalization():
    client, _ = _make_client({"data": [SAMPLE_PAPER]})
    entries = client.fetch_papers(query="digital twin")

    assert len(entries) == 1
    assert entries[0].arxiv_id == "2501.12345"
    assert entries[0].url == "https://arxiv.org/abs/2501.12345"


def test_fetch_papers_s2_url_fallback():
    client, _ = _make_client({"data": [SAMPLE_PAPER_NO_ARXIV]})
    entries = client.fetch_papers(query="some query")

    assert len(entries) == 1
    assert entries[0].arxiv_id is None
    assert entries[0].url == "https://www.semanticscholar.org/paper/xyz789"


def test_fetch_papers_rate_limit_raises():
    from src.infrastructure.collection.clients.semantic_scholar_client import (
        SemanticScholarClient,
        SemanticScholarRateLimitedError,
    )

    mock_http = MagicMock()
    mock_response_429 = Mock()
    mock_response_429.status_code = 429

    exc = requests.exceptions.HTTPError("429 Too Many Requests")
    exc.response = mock_response_429
    mock_http.get.side_effect = exc

    client = SemanticScholarClient(api_key=None, http_client=mock_http)

    with pytest.raises(SemanticScholarRateLimitedError):
        client.fetch_papers(query="test")


def test_fetch_papers_null_abstract():
    paper = dict(SAMPLE_PAPER)
    paper["abstract"] = None

    client, _ = _make_client({"data": [paper]})
    entries = client.fetch_papers(query="test")

    assert len(entries) == 1
    assert entries[0].abstract == ""


def test_fetch_papers_no_pdf():
    paper = dict(SAMPLE_PAPER)
    paper["openAccessPdf"] = None

    client, _ = _make_client({"data": [paper]})
    entries = client.fetch_papers(query="test")

    assert len(entries) == 1
    assert entries[0].open_access_pdf_url is None


def test_fetch_papers_empty_data():
    client, _ = _make_client({"data": []})
    entries = client.fetch_papers(query="test")

    assert entries == []


def test_fetch_papers_network_error():
    from src.infrastructure.collection.clients.semantic_scholar_client import SemanticScholarClient

    mock_http = MagicMock()
    mock_http.get.side_effect = Exception("Network failure")

    client = SemanticScholarClient(api_key=None, http_client=mock_http)
    entries = client.fetch_papers(query="test")

    assert entries == []
