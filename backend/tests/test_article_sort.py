"""Tests for citation_count and view_count sort in GET /articles."""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _mock_metrics(view_count=0):
    m = MagicMock()
    m.view_count = view_count
    return m


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
    metric_values = {"citation_count": citation} if citation is not None else {}
    return (_mock_article(title), _mock_metrics(views), metric_values, favorited)


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


def test_sort_arbitrary_metric_key_is_accepted():
    """2026-07-12: sort is no longer a fixed Literal — any catalog metric_key is a valid value,
    since the set of enabled metrics is deployment-defined, not known at the API-schema level."""
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])):
        r = _client().get("/articles?sort=impact_factor&order=desc")
    assert r.status_code == 200


def test_sort_unrecognized_value_does_not_error():
    """An unrecognized sort value degrades gracefully (no-op ordering), not a 422 — the API can no
    longer distinguish "invalid" from "a metric_key it doesn't know about yet" at request time."""
    with patch("backend.routers.articles.get_articles_paginated", return_value=(0, [])):
        r = _client().get("/articles?sort=totally_not_a_thing")
    assert r.status_code == 200


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
    assert item["metrics"]["citation_count"] == 150
    assert item["view_count"] == 10


def test_articles_response_includes_arbitrary_catalog_metrics():
    """2026-07-12: `metrics` is a generic map, not limited to citation_count."""
    row = (_mock_article("Multi-metric"), _mock_metrics(5), {"citation_count": 10, "impact_factor": 3.5}, None)
    with patch("backend.routers.articles.get_articles_paginated", return_value=(1, [row])):
        r = _client().get("/articles")
    item = r.json()["items"][0]
    assert item["metrics"] == {"citation_count": 10, "impact_factor": 3.5}
