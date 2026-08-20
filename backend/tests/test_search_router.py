"""
Unit tests for backend/routers/search.py — the FastAPI wiring itself (auth guard,
query-param parsing/defaults, empty-input validation, request->service argument
passthrough). backend/tests/test_search_service.py already covers the retrieval
logic in depth with a mocked DB session; backend/tests/integration/test_search.py
covers the real Postgres/pgvector/Redis round trip. Both search_articles_hybrid and
suggest_terms are patched on backend.routers.search (not backend.services.search_service)
since the router imports them by name (`from backend.services.search_service import
search_articles_hybrid, suggest_terms`), same reasoning as test_chat_router.py patching
backend.routers.chat._make_redis rather than the module it's defined in.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")


def _guest_headers():
    from backend.services.auth_service import create_guest_access_token
    return {"Authorization": f"Bearer {create_guest_access_token('test-guest-id')}"}


def _paginated_articles(total=0, page=1, size=20):
    from backend.schemas.article import PaginatedArticles
    return PaginatedArticles(items=[], total=total, page=page, size=size)


def _autocomplete_response(terms=()):
    from backend.schemas.search import AutocompleteResponse, SearchSuggestion
    return AutocompleteResponse(suggestions=[SearchSuggestion(term=t, occurrence_count=1) for t in terms])


# ---------------------------------------------------------------------------
# GET /search — auth
# ---------------------------------------------------------------------------


def test_search_requires_at_least_a_guest_token():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/search", params={"q": "test"})
    assert response.status_code == 401


def test_search_guest_token_is_sufficient():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.search.search_articles_hybrid", AsyncMock(return_value=_paginated_articles())):
        response = client.get("/search", params={"q": "test"}, headers=_guest_headers())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /search — empty query validation
# ---------------------------------------------------------------------------


def test_search_blank_query_returns_400():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        response = client.get("/search", params={"q": "   "}, headers=_guest_headers())
    assert response.status_code == 400
    mock_hybrid.assert_not_called()


def test_search_missing_query_param_returns_422():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/search", headers=_guest_headers())
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /search — happy path + param passthrough
# ---------------------------------------------------------------------------


def test_search_returns_paginated_envelope():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.search.search_articles_hybrid", AsyncMock(return_value=_paginated_articles(total=3))):
        response = client.get("/search", params={"q": "cyberattacks"}, headers=_guest_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["items"] == []


def test_search_passes_stripped_query_and_defaults_to_service():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get("/search", params={"q": "  cyberattacks  "}, headers=_guest_headers())

    _, kwargs = mock_hybrid.call_args
    assert kwargs["query"] == "cyberattacks"
    assert kwargs["page"] == 1
    assert kwargs["size"] == 20
    assert kwargs["exact_match_only"] is False
    assert kwargs["lang"] == "en"
    assert kwargs["sort"] is None
    assert kwargs["order"] == "desc"
    assert kwargs["aggregators"] is None
    assert kwargs["original_sources"] is None
    assert kwargs["tags"] is None
    assert kwargs["tag_groups"] is None


def test_search_passes_topic_id_page_and_size():
    from backend.main import app
    client = TestClient(app)
    topic_id = uuid.uuid4()
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get(
            "/search",
            params={"q": "test", "topic_id": str(topic_id), "page": 2, "size": 5},
            headers=_guest_headers(),
        )

    _, kwargs = mock_hybrid.call_args
    assert kwargs["topic_id"] == topic_id
    assert kwargs["page"] == 2
    assert kwargs["size"] == 5


def test_search_passes_exact_match_only_flag():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get("/search", params={"q": "test", "exact_match_only": "true"}, headers=_guest_headers())

    _, kwargs = mock_hybrid.call_args
    assert kwargs["exact_match_only"] is True


def test_search_passes_repeated_filter_params_as_lists():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get(
            "/search",
            params=[
                ("q", "test"),
                ("aggregator", "techcrunch"),
                ("aggregator", "arxiv"),
                ("original_source", "blog.a.com"),
                ("tag", "AI"),
                ("tag", "ML"),
                ("tag_group", "research"),
            ],
            headers=_guest_headers(),
        )

    _, kwargs = mock_hybrid.call_args
    assert kwargs["aggregators"] == ["techcrunch", "arxiv"]
    assert kwargs["original_sources"] == ["blog.a.com"]
    assert kwargs["tags"] == ["AI", "ML"]
    assert kwargs["tag_groups"] == ["research"]


def test_search_passes_date_range_params():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get(
            "/search",
            params={
                "q": "test",
                "published_after": "2024-01-01",
                "published_before": "2024-12-31",
                "scraped_after": "2024-06-01",
                "scraped_before": "2024-06-30",
            },
            headers=_guest_headers(),
        )

    _, kwargs = mock_hybrid.call_args
    assert str(kwargs["published_after"]) == "2024-01-01"
    assert str(kwargs["published_before"]) == "2024-12-31"
    assert str(kwargs["scraped_after"]) == "2024-06-01"
    assert str(kwargs["scraped_before"]) == "2024-06-30"


def test_search_passes_sort_order_and_lang():
    from backend.main import app
    client = TestClient(app)
    mock_hybrid = AsyncMock(return_value=_paginated_articles())
    with patch("backend.routers.search.search_articles_hybrid", mock_hybrid):
        client.get(
            "/search",
            params={"q": "test", "sort": "published_at", "order": "asc", "lang": "zh-TW"},
            headers=_guest_headers(),
        )

    _, kwargs = mock_hybrid.call_args
    assert kwargs["sort"] == "published_at"
    assert kwargs["order"] == "asc"
    assert kwargs["lang"] == "zh-TW"


# ---------------------------------------------------------------------------
# GET /search/autocomplete — auth
# ---------------------------------------------------------------------------


def test_autocomplete_requires_at_least_a_guest_token():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/search/autocomplete", params={"prefix": "lear"})
    assert response.status_code == 401


def test_autocomplete_guest_token_is_sufficient():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.search.suggest_terms", return_value=_autocomplete_response()):
        response = client.get("/search/autocomplete", params={"prefix": "lear"}, headers=_guest_headers())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /search/autocomplete — empty prefix validation
# ---------------------------------------------------------------------------


def test_autocomplete_blank_prefix_returns_400():
    from backend.main import app
    client = TestClient(app)
    mock_suggest = MagicMock(return_value=_autocomplete_response())
    with patch("backend.routers.search.suggest_terms", mock_suggest):
        response = client.get("/search/autocomplete", params={"prefix": "   "}, headers=_guest_headers())
    assert response.status_code == 400
    mock_suggest.assert_not_called()


def test_autocomplete_missing_prefix_param_returns_422():
    from backend.main import app
    client = TestClient(app)
    response = client.get("/search/autocomplete", headers=_guest_headers())
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /search/autocomplete — happy path + param passthrough
# ---------------------------------------------------------------------------


def test_autocomplete_returns_suggestions_envelope():
    from backend.main import app
    client = TestClient(app)
    with patch("backend.routers.search.suggest_terms", return_value=_autocomplete_response(["learning", "learned"])):
        response = client.get("/search/autocomplete", params={"prefix": "lear"}, headers=_guest_headers())
    assert response.status_code == 200
    data = response.json()
    assert [s["term"] for s in data["suggestions"]] == ["learning", "learned"]


def test_autocomplete_passes_stripped_prefix_topic_id_and_lang():
    from backend.main import app
    client = TestClient(app)
    topic_id = uuid.uuid4()
    mock_suggest = MagicMock(return_value=_autocomplete_response())
    with patch("backend.routers.search.suggest_terms", mock_suggest):
        client.get(
            "/search/autocomplete",
            params={"prefix": "  lear  ", "topic_id": str(topic_id), "lang": "zh-TW"},
            headers=_guest_headers(),
        )

    _, kwargs = mock_suggest.call_args
    assert kwargs["topic_id"] == topic_id
    assert kwargs["prefix"] == "lear"
    assert kwargs["lang"] == "zh-TW"


def test_autocomplete_defaults_lang_to_en():
    from backend.main import app
    client = TestClient(app)
    mock_suggest = MagicMock(return_value=_autocomplete_response())
    with patch("backend.routers.search.suggest_terms", mock_suggest):
        client.get("/search/autocomplete", params={"prefix": "lear"}, headers=_guest_headers())

    _, kwargs = mock_suggest.call_args
    assert kwargs["lang"] == "en"
