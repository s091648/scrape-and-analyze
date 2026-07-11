"""Tests for citation_count and view_count sort in GET /articles."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _mock_metrics(view_count=0):
    m = MagicMock()
    m.view_count = view_count
    return m


def _mock_citation_value(value=None):
    if value is None:
        return None
    v = MagicMock()
    v.value = value
    return v


def _mock_article(title="A"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.url = "https://example.com"
    a.source = "arxiv"
    a.title = title
    a.content = "body"
    a.published_at = datetime.now(timezone.utc)
    a.scraped_at = datetime.now(timezone.utc)
    a.metadata_ = None
    a.original_source = None
    return a


def _row(title="A", citation=None, views=0, favorited=None):
    return (_mock_article(title), _mock_metrics(views), _mock_citation_value(citation), favorited)


def _client():
    from backend.main import app
    return TestClient(app)


def test_sort_citation_count_is_accepted():
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])):
        r = _client().get("/articles?sort=citation_count&order=desc")
    assert r.status_code == 200


def test_sort_view_count_is_accepted():
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])):
        r = _client().get("/articles?sort=view_count&order=asc")
    assert r.status_code == 200


def test_sort_invalid_column_rejected():
    r = _client().get("/articles?sort=invalid_column")
    assert r.status_code == 422


def test_sort_citation_count_passes_correct_arg_to_service():
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])) as mock_svc:
        _client().get("/articles?sort=citation_count&order=desc")
    call_kwargs = mock_svc.call_args
    positional = call_kwargs[0]
    assert positional[1] == "citation_count"
    assert positional[2] == "desc"


def test_sort_view_count_passes_correct_arg_to_service():
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])) as mock_svc:
        _client().get("/articles?sort=view_count&order=asc")
    call_kwargs = mock_svc.call_args
    positional = call_kwargs[0]
    assert positional[1] == "view_count"
    assert positional[2] == "asc"


def test_citation_count_included_in_response():
    rows = [_row("Paper A", citation=150, views=10)]
    with patch("backend.routers.articles.get_articles_paginated", return_value=(1, rows)):
        r = _client().get("/articles?sort=citation_count&order=desc")
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["citation_count"] == 150
    assert item["view_count"] == 10
