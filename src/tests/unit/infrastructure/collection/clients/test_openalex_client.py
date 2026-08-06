import pytest
from unittest.mock import MagicMock, Mock
import requests.exceptions

# Abstract as inverted index: "A test abstract" → positions 0,1,2
SAMPLE_ABSTRACT_INDEX = {
    "A": [0],
    "test": [1],
    "abstract": [2],
}

SAMPLE_WORK = {
    "id": "https://openalex.org/W123456",
    "title": "Test Paper",
    "abstract_inverted_index": SAMPLE_ABSTRACT_INDEX,
    "authorships": [
        {"author": {"display_name": "Author One"}},
        {"author": {"display_name": "Author Two"}},
    ],
    "publication_date": "2025-01-15",
    "open_access": {"is_oa": True, "oa_url": "https://example.com/paper.pdf"},
    "doi": "https://doi.org/10.1234/test",
    "ids": {
        "openalex": "https://openalex.org/W123456",
        "doi": "https://doi.org/10.1234/test",
        "arxiv": "https://arxiv.org/abs/2501.12345",
    },
    "cited_by_count": 42,
    "primary_location": {"pdf_url": "https://example.com/paper.pdf"},
}

SAMPLE_WORK_NO_ARXIV = {
    "id": "https://openalex.org/W999999",
    "title": "No ArXiv Paper",
    "abstract_inverted_index": {"Another": [0], "abstract": [1]},
    "authorships": [{"author": {"display_name": "Author Three"}}],
    "publication_date": "2025-02-01",
    "open_access": {"is_oa": False, "oa_url": None},
    "doi": "https://doi.org/10.5678/other",
    "ids": {
        "openalex": "https://openalex.org/W999999",
        "doi": "https://doi.org/10.5678/other",
    },
    "cited_by_count": 5,
    "primary_location": {"pdf_url": None},
}


def _make_client(response_data: dict):
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient

    mock_response = MagicMock()
    mock_response.json.return_value = response_data

    mock_http = MagicMock()
    mock_http.get.return_value = mock_response

    return OpenAlexClient(mailto=None, http_client=mock_http), mock_http


def test_fetch_papers_returns_entries():
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient, OpenAlexEntry

    client, _ = _make_client({"results": [SAMPLE_WORK, SAMPLE_WORK_NO_ARXIV]})
    entries = client.fetch_papers(query="digital twin")

    assert len(entries) == 2
    assert all(isinstance(e, OpenAlexEntry) for e in entries)
    assert entries[0].work_id == "https://openalex.org/W123456"
    assert entries[0].title == "Test Paper"
    assert entries[0].authors == ["Author One", "Author Two"]
    assert entries[0].citation_count == 42
    assert entries[0].is_open_access is True


def test_fetch_papers_abstract_reconstructed():
    client, _ = _make_client({"results": [SAMPLE_WORK]})
    entries = client.fetch_papers(query="test")

    assert len(entries) == 1
    assert entries[0].abstract == "A test abstract"


def test_fetch_papers_arxiv_url_priority():
    client, _ = _make_client({"results": [SAMPLE_WORK]})
    entries = client.fetch_papers(query="test")

    assert entries[0].arxiv_id == "2501.12345"
    assert entries[0].url == "https://arxiv.org/abs/2501.12345"


def test_fetch_papers_doi_url_when_no_arxiv():
    client, _ = _make_client({"results": [SAMPLE_WORK_NO_ARXIV]})
    entries = client.fetch_papers(query="test")

    assert entries[0].arxiv_id is None
    assert entries[0].url == "https://doi.org/10.5678/other"
    assert entries[0].doi == "10.5678/other"


def test_fetch_papers_openalex_url_fallback():
    work = dict(SAMPLE_WORK_NO_ARXIV)
    work["ids"] = {"openalex": "https://openalex.org/W999999"}
    work["doi"] = None

    client, _ = _make_client({"results": [work]})
    entries = client.fetch_papers(query="test")

    assert entries[0].url == "https://openalex.org/W999999"


def test_fetch_papers_rate_limit_raises():
    from src.infrastructure.collection.clients.openalex_client import (
        OpenAlexClient,
        OpenAlexRateLimitedError,
    )

    mock_http = MagicMock()
    mock_response_429 = Mock()
    mock_response_429.status_code = 429

    exc = requests.exceptions.HTTPError("429 Too Many Requests")
    exc.response = mock_response_429
    mock_http.get.side_effect = exc

    client = OpenAlexClient(mailto=None, http_client=mock_http)

    with pytest.raises(OpenAlexRateLimitedError):
        client.fetch_papers(query="test")


def test_fetch_papers_null_abstract_index():
    work = dict(SAMPLE_WORK)
    work["abstract_inverted_index"] = None

    client, _ = _make_client({"results": [work]})
    entries = client.fetch_papers(query="test")

    assert len(entries) == 1
    assert entries[0].abstract == ""


def test_fetch_papers_no_pdf():
    work = dict(SAMPLE_WORK)
    work["primary_location"] = {"pdf_url": None}
    work["open_access"] = {"is_oa": True, "oa_url": None}

    client, _ = _make_client({"results": [work]})
    entries = client.fetch_papers(query="test")

    assert entries[0].open_access_pdf_url is None


def test_fetch_papers_empty_results():
    client, _ = _make_client({"results": []})
    entries = client.fetch_papers(query="test")

    assert entries == []


def test_fetch_papers_network_error():
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient

    mock_http = MagicMock()
    mock_http.get.side_effect = Exception("Network failure")

    client = OpenAlexClient(mailto=None, http_client=mock_http)
    entries = client.fetch_papers(query="test")

    assert entries == []


def test_fetch_papers_sends_mailto_in_user_agent():
    client, mock_http = _make_client({"results": []})
    client._mailto = "user@example.com"
    client.fetch_papers(query="test")

    call_kwargs = mock_http.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert "mailto:user@example.com" in headers.get("User-Agent", "")


# ---------------------------------------------------------------------------
# fetch_by_id — used by dedup_reconcile.py to detect upstream (OpenAlex) merges
# ---------------------------------------------------------------------------

def test_fetch_by_id_returns_raw_dict():
    client, mock_http = _make_client(SAMPLE_WORK)
    result = client.fetch_by_id("https://openalex.org/W123456")

    assert result == SAMPLE_WORK


def test_fetch_by_id_strips_full_url_to_short_id():
    client, mock_http = _make_client(SAMPLE_WORK)
    client.fetch_by_id("https://openalex.org/W123456")

    url = mock_http.get.call_args[0][0]
    assert url.endswith("/W123456")
    assert url.count("W123456") == 1  # not double-appended


def test_fetch_by_id_accepts_bare_short_id():
    client, mock_http = _make_client(SAMPLE_WORK)
    client.fetch_by_id("W123456")

    url = mock_http.get.call_args[0][0]
    assert url.endswith("/W123456")


def test_fetch_by_id_returns_merged_survivor_when_redirected():
    """The mechanism dedup_reconcile.py relies on: OpenAlex transparently
    redirects a merged-away work_id, so `requests` (followed by default)
    returns the survivor's data — whose `id` differs from what was requested."""
    survivor = dict(SAMPLE_WORK_NO_ARXIV)  # id: W999999
    client, _ = _make_client(survivor)

    result = client.fetch_by_id("https://openalex.org/W123456")  # requested a different, merged-away id

    assert result["id"] == "https://openalex.org/W999999"


def test_fetch_by_id_rate_limit_raises():
    from src.infrastructure.collection.clients.openalex_client import (
        OpenAlexClient,
        OpenAlexRateLimitedError,
    )

    mock_http = MagicMock()
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    exc = requests.exceptions.HTTPError("429 Too Many Requests")
    exc.response = mock_response_429
    mock_http.get.side_effect = exc

    client = OpenAlexClient(mailto=None, http_client=mock_http)

    with pytest.raises(OpenAlexRateLimitedError):
        client.fetch_by_id("W123456")


def test_fetch_by_id_network_error_returns_none():
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient

    mock_http = MagicMock()
    mock_http.get.side_effect = Exception("Network failure")

    client = OpenAlexClient(mailto=None, http_client=mock_http)
    result = client.fetch_by_id("W123456")

    assert result is None


def test_fetch_by_id_bad_json_returns_none():
    from src.infrastructure.collection.clients.openalex_client import OpenAlexClient

    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("not json")
    mock_http = MagicMock()
    mock_http.get.return_value = mock_response

    client = OpenAlexClient(mailto=None, http_client=mock_http)
    result = client.fetch_by_id("W123456")

    assert result is None


def test_reconstruct_abstract_ordering():
    from src.infrastructure.collection.clients.openalex_client import _reconstruct_abstract

    index = {"hello": [1], "world": [2], "say": [0]}
    result = _reconstruct_abstract(index)
    assert result == "say hello world"


def test_reconstruct_abstract_empty():
    from src.infrastructure.collection.clients.openalex_client import _reconstruct_abstract

    assert _reconstruct_abstract(None) == ""
    assert _reconstruct_abstract({}) == ""
