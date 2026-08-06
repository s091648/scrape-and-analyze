from unittest.mock import MagicMock

from src.infrastructure.collection.clients.arxiv_client import ArxivClient

ATOM_ENTRY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2606.29232v1</id>
    <title>A Paper About Digital Twins</title>
    <summary>An abstract.</summary>
    <published>2026-06-15T00:00:00Z</published>
    <author><name>Alice</name></author>
    <link rel="alternate" href="http://arxiv.org/abs/2606.29232v1"/>
  </entry>
</feed>
"""


def _make_client(xml=ATOM_ENTRY):
    mock_http = MagicMock()
    mock_http.get.return_value = MagicMock(content=xml.encode("utf-8"))
    return ArxivClient(http_client=mock_http), mock_http


def test_fetch_entries_normalizes_arxiv_id_to_bare_id():
    """The Atom <id> element is a full URL (e.g. "http://arxiv.org/abs/2606.29232v1"),
    not a bare identifier. ArxivEntry.arxiv_id must strip the URL prefix and version
    suffix — external lookups like Semantic Scholar's paper/ARXIV:<id> 404 otherwise
    (see semantic_scholar_fetch_by_arxiv_id_failed in production logs)."""
    client, _ = _make_client()
    entries = client.fetch_entries(query="cat:cs.LG")

    assert len(entries) == 1
    assert entries[0].arxiv_id == "2606.29232"


def test_fetch_entries_keeps_full_url_for_url_and_pdf_url():
    """url/pdf_url must stay full URLs even though arxiv_id is normalized to a bare id."""
    client, _ = _make_client()
    entries = client.fetch_entries(query="cat:cs.LG")

    assert entries[0].url == "http://arxiv.org/abs/2606.29232v1"
    assert entries[0].pdf_url == "http://arxiv.org/pdf/2606.29232v1"


def test_fetch_entries_strips_version_suffix_from_arxiv_id():
    xml = ATOM_ENTRY.replace("2606.29232v1", "2606.29232v3")
    client, _ = _make_client(xml)
    entries = client.fetch_entries(query="cat:cs.LG")

    assert entries[0].arxiv_id == "2606.29232"
