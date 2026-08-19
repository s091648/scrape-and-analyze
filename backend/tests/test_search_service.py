"""
Unit tests for backend/services/search_service.py.

Query-builder SQL shape and the _rrf_merge helper are tested here with a mocked
DB session — real pgvector cosine-distance behavior and the real term->article
inverted index (intelligence.search_terms/search_term_articles) are covered by the
integration test in backend/tests/integration/test_search.py.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest


def _fake_embed(sparse, dense):
    """Builds an async embed_query replacement returning a fixed (sparse, dense) pair —
    embed_query is async (023-article-search follow-up: it now calls chatbot_plugin_sdk
    provider .embed() coroutines), so a plain lambda can no longer stand in for it."""
    async def _embed(q):
        return sparse, dense
    return _embed


class _FakeProvider:
    """Stand-in for a chatbot_plugin_sdk embedding provider (GeminiDenseProvider /
    EndpointProvider) — both expose an async embed(texts) -> list."""
    def __init__(self, result):
        self._result = result

    async def embed(self, texts):
        return self._result


# ---------------------------------------------------------------------------
# _build_dense_provider / _build_sparse_provider
# ---------------------------------------------------------------------------

def test_build_dense_provider_returns_none_when_provider_type_empty(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "RAG_DENSE_PROVIDER", "")
    assert search_service._build_dense_provider() is None


def test_build_sparse_provider_returns_none_when_provider_type_empty(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "RAG_SPARSE_PROVIDER", "")
    assert search_service._build_sparse_provider() is None


def test_build_dense_provider_passes_config_to_sdk_factory(monkeypatch):
    """Regression guard for the root cause behind the "occurrence_count doesn't match
    search results" investigation: the query embedding MUST use the identical provider/
    model/dimension as src/'s RAG ingestion pipeline, or the query vector lands in a
    different space than the stored article vectors."""
    from backend.services import search_service

    monkeypatch.setattr(search_service, "RAG_DENSE_PROVIDER", "gemini")
    monkeypatch.setattr(search_service, "RAG_DENSE_MODEL", "gemini-embedding-001")
    monkeypatch.setattr(search_service, "RAG_DENSE_DIMENSION", 768)
    monkeypatch.setattr(search_service, "RAG_DENSE_API_KEY_ENV", "RAG_GEMINI_API_KEY")
    monkeypatch.setenv("RAG_GEMINI_API_KEY", "test-key")

    captured = {}

    def fake_build_dense_provider(config):
        captured.update(config)
        return "sentinel-dense-provider"

    with patch("chatbot_plugin_sdk.build_dense_provider", fake_build_dense_provider):
        result = search_service._build_dense_provider()

    assert result == "sentinel-dense-provider"
    assert captured["provider_type"] == "gemini"
    assert captured["model"] == "gemini-embedding-001"
    assert captured["dimension"] == 768
    assert captured["api_key"] == "test-key"


def test_build_sparse_provider_passes_config_to_sdk_factory(monkeypatch):
    from backend.services import search_service

    monkeypatch.setattr(search_service, "RAG_SPARSE_PROVIDER", "endpoint")
    monkeypatch.setattr(search_service, "RAG_SPARSE_DIMENSION", 30522)
    monkeypatch.setattr(search_service, "RAG_SPARSE_ENDPOINT_URL", "http://fastembed:8080")

    captured = {}

    def fake_build_sparse_provider(config):
        captured.update(config)
        return "sentinel-sparse-provider"

    with patch("chatbot_plugin_sdk.build_sparse_provider", fake_build_sparse_provider):
        result = search_service._build_sparse_provider()

    assert result == "sentinel-sparse-provider"
    assert captured["provider_type"] == "endpoint"
    assert captured["dimension"] == 30522
    assert captured["endpoint_url"] == "http://fastembed:8080"


# ---------------------------------------------------------------------------
# embed_query — orchestrates the dense + sparse providers concurrently
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_query_returns_dense_and_sparse_from_configured_providers(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "_build_dense_provider", lambda: _FakeProvider([[0.1, 0.2, 0.3]]))
    monkeypatch.setattr(search_service, "_build_sparse_provider", lambda: _FakeProvider([{"1": 0.5, "42": 0.3}]))

    sparse, dense = await search_service.embed_query("test query")

    assert dense == [0.1, 0.2, 0.3]
    assert sparse == {"1": 0.5, "42": 0.3}


@pytest.mark.asyncio
async def test_embed_query_returns_none_dense_when_dense_provider_unconfigured(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "_build_dense_provider", lambda: None)
    monkeypatch.setattr(search_service, "_build_sparse_provider", lambda: _FakeProvider([{"1": 0.5}]))

    sparse, dense = await search_service.embed_query("test query")

    assert dense is None
    assert sparse == {"1": 0.5}


@pytest.mark.asyncio
async def test_embed_query_returns_none_sparse_when_sparse_provider_unconfigured(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "_build_dense_provider", lambda: _FakeProvider([[0.1]]))
    monkeypatch.setattr(search_service, "_build_sparse_provider", lambda: None)

    sparse, dense = await search_service.embed_query("test query")

    assert dense == [0.1]
    assert sparse is None


@pytest.mark.asyncio
async def test_embed_query_returns_both_none_when_neither_provider_configured(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "_build_dense_provider", lambda: None)
    monkeypatch.setattr(search_service, "_build_sparse_provider", lambda: None)

    sparse, dense = await search_service.embed_query("test query")

    assert sparse is None
    assert dense is None


# ---------------------------------------------------------------------------
# _sparse_vec_literal / _dense_vec_literal
# ---------------------------------------------------------------------------

def test_sparse_vec_literal_formats_pgvector_wire_format():
    from backend.services.search_service import _sparse_vec_literal
    assert _sparse_vec_literal({0: 0.5, 1: 0.3}, dim=30522) == "{0:0.5,1:0.3}/30522"


def test_sparse_vec_literal_omits_zero_weights():
    from backend.services.search_service import _sparse_vec_literal
    assert _sparse_vec_literal({0: 0.5, 1: 0.0}, dim=30522) == "{0:0.5}/30522"


def test_dense_vec_literal_formats_pgvector_wire_format():
    from backend.services.search_service import _dense_vec_literal
    assert _dense_vec_literal([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"


# ---------------------------------------------------------------------------
# _run_vector_query — SQL shape
# ---------------------------------------------------------------------------

def test_run_vector_query_uses_cosine_operator_not_inner_product():
    """Critical operator-class pitfall (research.md) — both this repo's HNSW indexes
    use sparsevec_cosine_ops/vector_cosine_ops, so the query MUST use `<=>`, never `<#>`."""
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _run_vector_query(db, "sparse_vector", "sparsevec", "{0:1.0}/30522", topic_id=None, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    assert "<=>" in sql_text
    assert "<#>" not in sql_text


def test_run_vector_query_includes_topic_filter_when_topic_id_given():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []
    topic_id = uuid.uuid4()

    _run_vector_query(db, "dense_vector", "vector", "[0.1]", topic_id=topic_id, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    params = db.execute.call_args[0][1]
    assert "a.topic_id = :topic_id" in sql_text
    assert params["topic_id"] == str(topic_id)


def test_run_vector_query_omits_topic_filter_when_topic_id_none():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _run_vector_query(db, "dense_vector", "vector", "[0.1]", topic_id=None, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    assert "topic_id" not in sql_text


def test_run_vector_query_excludes_tombstoned_and_null_vector_rows():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _run_vector_query(db, "sparse_vector", "sparsevec", "{0:1.0}/30522", topic_id=None, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    assert "a.merged_into_id IS NULL" in sql_text
    assert "ac.sparse_vector IS NOT NULL" in sql_text


def test_run_vector_query_dedups_per_article_via_group_by_min_distance():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _run_vector_query(db, "sparse_vector", "sparsevec", "{0:1.0}/30522", topic_id=None, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    assert "GROUP BY a.id" in sql_text
    assert "MIN(ac.sparse_vector" in sql_text


# ---------------------------------------------------------------------------
# _rrf_merge
# ---------------------------------------------------------------------------

def _row(article_id, **kwargs):
    r = {"id": article_id, "url": "u", "source": "s", "title": "t", "content": "c",
         "published_at": None, "scraped_at": None}
    r.update(kwargs)
    return r


def test_rrf_merge_ranks_article_present_in_both_lists_highest():
    from backend.services.search_service import _rrf_merge
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    dense_rows = [_row(a), _row(b)]
    sparse_rows = [_row(a), _row(c)]

    merged = _rrf_merge(dense_rows, sparse_rows)
    ids_in_order = [row["id"] for row, _score in merged]

    assert ids_in_order[0] == a  # appears in both lists -> highest combined score
    assert set(ids_in_order) == {a, b, c}


def test_rrf_merge_score_matches_formula():
    from backend.services.search_service import _rrf_merge
    a = uuid.uuid4()
    merged = _rrf_merge([_row(a)], [], k=60)
    # rank 0 in dense only: 1/(60+0+1)
    assert merged[0][1] == pytest.approx(1 / 61)


def test_rrf_merge_handles_empty_lists():
    from backend.services.search_service import _rrf_merge
    assert _rrf_merge([], []) == []


def test_rrf_merge_term_only_in_one_list_still_included():
    from backend.services.search_service import _rrf_merge
    a = uuid.uuid4()
    merged = _rrf_merge([], [_row(a)])
    assert len(merged) == 1
    assert merged[0][0]["id"] == a


# ---------------------------------------------------------------------------
# _exact_match_article_ids — the term->article inverted index AND-intersection lookup
# (023-article-search follow-up). Mocks the ORM query chain (db.query(...).join(...)
# .filter(...).group_by(...).having(...).all()) rather than hitting a real Postgres —
# real AND-intersection semantics over real rows are covered by the integration test.
# ---------------------------------------------------------------------------

def _mock_query_chain(db, rows):
    """Configures a MagicMock db so db.query(...).join(...).filter(...).filter(...)
    .group_by(...).having(...).all() (and every prefix of that chain) returns `rows`."""
    chain = db.query.return_value
    for attr in ("join", "filter", "group_by", "having"):
        getattr(chain, attr).return_value = chain
    chain.all.return_value = rows


def test_exact_match_article_ids_returns_none_when_query_tokenizes_to_nothing():
    from backend.services.search_service import _exact_match_article_ids
    db = MagicMock()

    result = _exact_match_article_ids(db, "a an the", topic_id=uuid.uuid4(), lang="en")

    assert result is None
    db.query.assert_not_called()  # short-circuits before touching the DB at all


def test_exact_match_article_ids_returns_article_ids_from_query(monkeypatch):
    from backend.services import search_service
    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "tokenize", lambda q: {"cyberattacks"})
    db = MagicMock()
    _mock_query_chain(db, [MagicMock(article_id=a), MagicMock(article_id=b)])

    result = search_service._exact_match_article_ids(db, "cyberattacks", topic_id=uuid.uuid4(), lang="en")

    assert result == {a, b}


def test_exact_match_article_ids_filters_by_language(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "tokenize", lambda q: {"機器學習"})
    db = MagicMock()
    _mock_query_chain(db, [])

    search_service._exact_match_article_ids(db, "機器學習", topic_id=uuid.uuid4(), lang="zh-TW")

    filter_calls = [str(call) for call in db.query.return_value.filter.call_args_list]
    assert any("zh-TW" in c or "language" in c for c in filter_calls) or db.query.return_value.filter.called


def test_exact_match_article_ids_omits_topic_filter_when_topic_id_none(monkeypatch):
    """Mirrors _run_vector_query's own topic_id=None behavior — a global (cross-topic)
    query must not be silently scoped to nothing."""
    from backend.services import search_service
    monkeypatch.setattr(search_service, "tokenize", lambda q: {"learning"})
    db = MagicMock()
    chain = db.query.return_value
    filter_call_count = {"n": 0}

    def _filter(*args, **kwargs):
        filter_call_count["n"] += 1
        return chain
    chain.join.return_value = chain
    chain.filter.side_effect = _filter
    chain.group_by.return_value = chain
    chain.having.return_value = chain
    chain.all.return_value = []

    search_service._exact_match_article_ids(db, "learning", topic_id=None, lang="en")

    # Exactly one .filter() call (language + term) — no second call adding a topic_id filter.
    assert filter_call_count["n"] == 1


# ---------------------------------------------------------------------------
# _fetch_articles_by_ids — raw SQL against core.articles (not the ORM — matches this
# file's existing convention for every other core.articles/vectors.* query, and avoids
# a schema_translate_map mismatch against intelligence.search_term_articles' ORM-sourced
# article_ids in the integration test harness — see the function's own docstring).
# ---------------------------------------------------------------------------

def test_fetch_articles_by_ids_returns_empty_list_for_empty_ids():
    from backend.services.search_service import _fetch_articles_by_ids
    db = MagicMock()

    result = _fetch_articles_by_ids(db, set(), topic_id=None)

    assert result == []
    db.execute.assert_not_called()


def test_fetch_articles_by_ids_orders_by_published_at_desc():
    from backend.services.search_service import _fetch_articles_by_ids
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _fetch_articles_by_ids(db, {uuid.uuid4()}, topic_id=None)

    sql_text = str(db.execute.call_args[0][0])
    assert "ORDER BY published_at DESC" in sql_text
    assert "merged_into_id IS NULL" in sql_text


def test_fetch_articles_by_ids_includes_topic_filter_when_given():
    from backend.services.search_service import _fetch_articles_by_ids
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []
    topic_id = uuid.uuid4()

    _fetch_articles_by_ids(db, {uuid.uuid4()}, topic_id=topic_id)

    sql_text = str(db.execute.call_args[0][0])
    params = db.execute.call_args[0][1]
    assert "topic_id = :topic_id" in sql_text
    assert params["topic_id"] == str(topic_id)


# ---------------------------------------------------------------------------
# search_articles_hybrid — orchestration (mocked embed + query calls). Results are
# ordered purely by RRF score (023-article-search follow-up: an earlier revision added
# literal-match candidate injection + a boost_exact_match reorder step on top of RRF —
# both deliberately reverted). `exact_match` is annotated via the term->article inverted
# index (_exact_match_article_ids), monkeypatched directly in these tests so they don't
# need a real Postgres round trip.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_articles_hybrid_paginates_merged_results(monkeypatch):
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed({1: 1.0}, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: set())
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [_row(a)] if column == "sparse_vector" else [_row(b)],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(db, query="test", topic_id=None, page=1, size=1)

    assert result.total == 2
    assert len(result.items) == 1  # page size 1


@pytest.mark.asyncio
async def test_search_articles_hybrid_keeps_pure_rrf_order(monkeypatch):
    """No re-ranking on top of RRF — an exact match with a lower RRF score stays behind
    a semantic-only neighbor with a higher one."""
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: {a})
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [
            _row(b, title="semantic neighbor"), _row(a, title="cyberattacks explained"),
        ],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(db, query="cyberattacks", topic_id=None, page=1, size=10)

    assert [item.id for item in result.items] == [b, a]  # RRF rank order, untouched


@pytest.mark.asyncio
async def test_search_articles_hybrid_sets_exact_match_flag_from_inverted_index(monkeypatch):
    """RRF's sparse+dense hybrid can surface semantic neighbors that never literally
    contain the query — exact_match (now sourced from the term->article inverted index,
    not a substring check) lets the frontend distinguish and filter them."""
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed({1: 1.0}, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: {a})
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [
            _row(a, title="Cyberattacks on IoT"), _row(b, title="unrelated semantic neighbor"),
        ],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(db, query="cyberattacks", topic_id=None, page=1, size=10)

    by_id = {item.id: item.exact_match for item in result.items}
    assert by_id[a] is True
    assert by_id[b] is False


@pytest.mark.asyncio
async def test_search_articles_hybrid_treats_none_exact_match_ids_as_empty(monkeypatch):
    """_exact_match_article_ids returns None when the query tokenizes to nothing — must
    not crash the RRF path, and every item's exact_match must come back False."""
    from backend.services import search_service

    a = uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed({1: 1.0}, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [_row(a)],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(db, query="a an the", topic_id=None, page=1, size=10)

    assert result.items[0].exact_match is False


# ---------------------------------------------------------------------------
# search_articles_hybrid — exact_match_only now delegates to a fully separate retrieval
# path (_search_exact_match_only) over the inverted index, bypassing RRF/vector
# retrieval entirely (023-article-search follow-up: RRF's candidate_k bound and
# embedding-space ranking gave no guarantee a literal match was even in RRF's
# candidates — see search_service.py's module-level design docstrings).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_articles_hybrid_exact_match_only_does_not_call_embed_query(monkeypatch):
    """The whole point of the separate retrieval path: exact_match_only=True must never
    touch the embedding providers or vectors.article_chunks at all."""
    from backend.services import search_service

    embed_called = {"n": 0}

    async def _tracking_embed(q):
        embed_called["n"] += 1
        return None, [0.1]
    monkeypatch.setattr(search_service, "embed_query", _tracking_embed)
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: set())

    db = MagicMock()
    await search_service.search_articles_hybrid(
        db, query="cyberattacks", topic_id=None, page=1, size=10, exact_match_only=True,
    )

    assert embed_called["n"] == 0


@pytest.mark.asyncio
async def test_search_articles_hybrid_exact_match_only_returns_empty_when_no_candidates(monkeypatch):
    from backend.services import search_service
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: set())

    db = MagicMock()
    result = await search_service.search_articles_hybrid(
        db, query="cyberattacks", topic_id=None, page=1, size=10, exact_match_only=True,
    )

    assert result.items == []
    assert result.total == 0


def _article_row(article_id, title="Cyberattacks Explained"):
    """Stand-in for one row of _fetch_articles_by_ids' raw-SQL .mappings() result."""
    return {
        "id": article_id, "url": "https://example.com/a", "source": "techcrunch",
        "title": title, "content": "an article about cyberattacks",
        "published_at": None, "scraped_at": None,
    }


@pytest.mark.asyncio
async def test_search_articles_hybrid_exact_match_only_paginates_over_inverted_index_candidates(monkeypatch):
    from backend.services import search_service

    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: {a, b, c})
    monkeypatch.setattr(
        search_service, "_fetch_articles_by_ids",
        lambda db, ids, topic_id: [_article_row(a), _article_row(b), _article_row(c)],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(
        db, query="cyberattacks", topic_id=None, page=1, size=2, exact_match_only=True,
    )

    assert result.total == 3
    assert len(result.items) == 2  # page size 2
    assert all(item.exact_match is True for item in result.items)


@pytest.mark.asyncio
async def test_search_articles_hybrid_exact_match_only_false_uses_rrf_path(monkeypatch):
    """Default (False) must not change existing RRF behavior — a zero-behavior-change
    guarantee for every caller that doesn't pass the new parameter."""
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: {a})
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [
            _row(a, title="cyberattacks explained"), _row(b, title="semantic neighbor"),
        ],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(db, query="cyberattacks", topic_id=None, page=1, size=10)

    assert result.total == 2  # both RRF candidates present — no exact-match filtering applied


# ---------------------------------------------------------------------------
# _filtered_article_ids — aggregator/original_source/tag/tag_group/date-range filters,
# the search endpoint's own counterpart to get_articles_paginated's filter-building block
# (backend/services/article_service.py) — added because GET /search silently ignored every
# filter/sort param the frontend already sent (023-article-search follow-up regression:
# filters/sort applied while browsing were dropped entirely the moment a search was active).
# ---------------------------------------------------------------------------

def _mock_id_execute(db, ids):
    """db.execute(text(...), params).mappings().all() -> rows with an "id" key — matches
    _fetch_articles_by_ids' own raw-SQL mocking style in this file."""
    db.execute.return_value.mappings.return_value.all.return_value = [{"id": i} for i in ids]


def test_filtered_article_ids_returns_none_when_no_filters_given():
    from backend.services.search_service import _filtered_article_ids
    db = MagicMock()

    result = _filtered_article_ids(db, None, None, None, None, None, None, None, None, None)

    assert result is None
    db.execute.assert_not_called()


def test_filtered_article_ids_filters_by_aggregator():
    from backend.services.search_service import _filtered_article_ids
    a, b = uuid.uuid4(), uuid.uuid4()
    db = MagicMock()
    _mock_id_execute(db, [a, b])

    result = _filtered_article_ids(db, None, ["techcrunch"], None, None, None, None, None, None, None)

    assert result == {a, b}
    sql_text = str(db.execute.call_args[0][0])
    assert "a.source IN" in sql_text
    assert db.execute.call_args[0][1]["aggregators"] == ["techcrunch"]


def test_filtered_article_ids_filters_by_date_range():
    from backend.services.search_service import _filtered_article_ids
    import datetime
    a = uuid.uuid4()
    db = MagicMock()
    _mock_id_execute(db, [a])

    result = _filtered_article_ids(
        db, None, None, None, None, None,
        datetime.date(2026, 1, 1), None, None, None,
    )

    assert result == {a}
    sql_text = str(db.execute.call_args[0][0])
    assert "a.published_at >=" in sql_text


def test_filtered_article_ids_filters_by_tags_and_tag_groups():
    from backend.services.search_service import _filtered_article_ids
    a = uuid.uuid4()
    db = MagicMock()
    _mock_id_execute(db, [a])

    result = _filtered_article_ids(db, None, None, None, ["AI", "ML"], ["research"], None, None, None, None)

    assert result == {a}
    sql_text = str(db.execute.call_args[0][0])
    params = db.execute.call_args[0][1]
    assert sql_text.count("intelligence.article_tags") == 3  # 2 tags + 1 tag_group
    assert params["tag_0"] == "AI"
    assert params["tag_1"] == "ML"
    assert params["tag_group_0"] == "research"


def test_filtered_article_ids_returns_empty_set_when_nothing_matches():
    from backend.services.search_service import _filtered_article_ids
    db = MagicMock()
    _mock_id_execute(db, [])

    result = _filtered_article_ids(db, None, ["nonexistent-source"], None, None, None, None, None, None, None)

    assert result == set()  # distinct from None ("no filter requested")


def test_filtered_article_ids_scopes_by_topic_when_given():
    from backend.services.search_service import _filtered_article_ids
    a = uuid.uuid4()
    topic_id = uuid.uuid4()
    db = MagicMock()
    _mock_id_execute(db, [a])

    _filtered_article_ids(db, topic_id, ["techcrunch"], None, None, None, None, None, None, None)

    sql_text = str(db.execute.call_args[0][0])
    params = db.execute.call_args[0][1]
    assert "a.topic_id = :topic_id" in sql_text
    assert params["topic_id"] == str(topic_id)


# ---------------------------------------------------------------------------
# _run_vector_query — id_filter (filtered_ids) SQL shape
# ---------------------------------------------------------------------------

def test_run_vector_query_includes_id_filter_when_filtered_ids_given():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []
    a, b = uuid.uuid4(), uuid.uuid4()

    _run_vector_query(db, "dense_vector", "vector", "[0.1]", topic_id=None, candidate_k=30, filtered_ids={a, b})

    sql_text = str(db.execute.call_args[0][0])
    params = db.execute.call_args[0][1]
    # bindparams(expanding=True) renders as a POSTCOMPILE placeholder, not literally ":filtered_ids"
    assert "a.id IN" in sql_text
    assert "filtered_ids" in sql_text
    assert set(params["filtered_ids"]) == {a, b}


def test_run_vector_query_omits_id_filter_when_filtered_ids_none():
    from backend.services.search_service import _run_vector_query
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = []

    _run_vector_query(db, "dense_vector", "vector", "[0.1]", topic_id=None, candidate_k=30)

    sql_text = str(db.execute.call_args[0][0])
    assert "filtered_ids" not in sql_text


# ---------------------------------------------------------------------------
# _reorder_by_field
# ---------------------------------------------------------------------------

def test_reorder_by_field_returns_items_unchanged_when_sort_is_none():
    from backend.services.search_service import _reorder_by_field
    items = [{"title": "b"}, {"title": "a"}]
    assert _reorder_by_field(items, None, "desc", key_fn=lambda x: x["title"]) == items


def test_reorder_by_field_returns_items_unchanged_when_sort_not_sortable():
    from backend.services.search_service import _reorder_by_field
    items = [{"view_count": 2}, {"view_count": 1}]
    assert _reorder_by_field(items, "view_count", "desc", key_fn=lambda x: x["view_count"]) == items


def test_reorder_by_field_sorts_ascending():
    from backend.services.search_service import _reorder_by_field
    items = [{"title": "b"}, {"title": "a"}, {"title": "c"}]
    result = _reorder_by_field(items, "title", "asc", key_fn=lambda x: x["title"])
    assert [i["title"] for i in result] == ["a", "b", "c"]


def test_reorder_by_field_sorts_descending():
    from backend.services.search_service import _reorder_by_field
    items = [{"title": "b"}, {"title": "a"}, {"title": "c"}]
    result = _reorder_by_field(items, "title", "desc", key_fn=lambda x: x["title"])
    assert [i["title"] for i in result] == ["c", "b", "a"]


def test_reorder_by_field_sorts_nulls_last_regardless_of_direction():
    from backend.services.search_service import _reorder_by_field
    items = [{"published_at": None}, {"published_at": 2}, {"published_at": 1}]

    asc = _reorder_by_field(items, "published_at", "asc", key_fn=lambda x: x["published_at"])
    assert [i["published_at"] for i in asc] == [1, 2, None]

    desc = _reorder_by_field(items, "published_at", "desc", key_fn=lambda x: x["published_at"])
    assert [i["published_at"] for i in desc] == [2, 1, None]


# ---------------------------------------------------------------------------
# search_articles_hybrid — filters/sort wired through to the retrieval paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_articles_hybrid_passes_filtered_ids_to_run_vector_query(monkeypatch):
    from backend.services import search_service

    filtered = {uuid.uuid4()}
    monkeypatch.setattr(search_service, "_filtered_article_ids", lambda *a, **k: filtered)
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: set())

    captured = {}

    def _capture_run_vector_query(db, column, cast, vec, topic_id, candidate_k, filtered_ids=None):
        captured["filtered_ids"] = filtered_ids
        return []
    monkeypatch.setattr(search_service, "_run_vector_query", _capture_run_vector_query)

    db = MagicMock()
    await search_service.search_articles_hybrid(
        db, query="test", topic_id=None, page=1, size=10, aggregators=["techcrunch"],
    )

    assert captured["filtered_ids"] == filtered


@pytest.mark.asyncio
async def test_search_articles_hybrid_reorders_rrf_results_when_sort_given(monkeypatch):
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "_filtered_article_ids", lambda *a, **k: None)
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *a, **k: set())
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, filtered_ids=None: [
            _row(a, title="z-title"), _row(b, title="a-title"),
        ],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(
        db, query="test", topic_id=None, page=1, size=10, sort="title", order="asc",
    )

    assert [item.title for item in result.items] == ["a-title", "z-title"]


@pytest.mark.asyncio
async def test_search_articles_hybrid_exact_match_only_applies_filtered_ids(monkeypatch):
    from backend.services import search_service

    a, b = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(search_service, "_filtered_article_ids", lambda *args, **kwargs: {a})
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: {a, b})
    monkeypatch.setattr(
        search_service, "_fetch_articles_by_ids",
        lambda db, ids, topic_id: [_article_row(i) for i in ids],
    )

    db = MagicMock()
    result = await search_service.search_articles_hybrid(
        db, query="cyberattacks", topic_id=None, page=1, size=10,
        exact_match_only=True, aggregators=["techcrunch"],
    )

    assert result.total == 1  # b excluded — not in the filtered set


# ---------------------------------------------------------------------------
# search_articles_hybrid — translation-aware (non-English `lang`) — display only.
# exact_match is no longer translation-substring-based (that's _exact_match_article_ids'
# job now, gated by `lang` at the inverted-index level instead) — these tests only cover
# translated_title/translated_content surfacing.
# ---------------------------------------------------------------------------

def _mock_db_with_translations(rows):
    """rows: list of {"article_id", "title", "content"} dicts, as _fetch_translations'
    raw SQL (db.execute(...).mappings().all()) would return them."""
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = rows
    return db


@pytest.mark.asyncio
async def test_search_articles_hybrid_returns_translated_title_and_content_for_non_english_lang(monkeypatch):
    from backend.services import search_service

    a = uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [_row(a, title="English Title", content="English content")],
    )
    db = _mock_db_with_translations([{"article_id": str(a), "title": "中文標題", "content": "中文內容"}])

    result = await search_service.search_articles_hybrid(db, query="中文", topic_id=None, page=1, size=10, lang="zh-TW")

    assert result.items[0].translated_title == "中文標題"
    assert result.items[0].translated_content == "中文內容"


@pytest.mark.asyncio
async def test_search_articles_hybrid_does_not_query_translations_for_english_lang(monkeypatch):
    """lang='en' (the default) must skip the translation lookup entirely — a zero-behavior-
    change guarantee for every existing English-only caller. Note db.query() (the ORM,
    used by _exact_match_article_ids) is monkeypatched away here; only db.execute()
    (_fetch_translations' raw SQL) is asserted on."""
    from backend.services import search_service

    a = uuid.uuid4()
    monkeypatch.setattr(search_service, "embed_query", _fake_embed(None, [0.1]))
    monkeypatch.setattr(search_service, "_exact_match_article_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(
        search_service, "_run_vector_query",
        lambda db, column, cast, vec, topic_id, candidate_k, **kwargs: [_row(a)],
    )
    db = MagicMock()

    await search_service.search_articles_hybrid(db, query="test", topic_id=None, page=1, size=10)

    db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# _prefix_suggestable_for_lang / suggest_terms — lang-gated autocomplete
# (023-article-search follow-up): a CJK prefix can only ever literally match via a
# translation for a specific `lang` (search_articles_hybrid's own lang-gating — see
# above), so suggesting one while the UI is in a non-Chinese locale would offer a
# suggestion that leads to a dead-end search.
# ---------------------------------------------------------------------------

def test_prefix_suggestable_for_lang_true_for_non_cjk_prefix_regardless_of_lang():
    from backend.services.search_service import _prefix_suggestable_for_lang
    assert _prefix_suggestable_for_lang("lear", "en") is True
    assert _prefix_suggestable_for_lang("lear", "zh-TW") is True


def test_prefix_suggestable_for_lang_false_for_cjk_prefix_when_lang_not_chinese():
    from backend.services.search_service import _prefix_suggestable_for_lang
    assert _prefix_suggestable_for_lang("遊戲", "en") is False


def test_prefix_suggestable_for_lang_true_for_cjk_prefix_when_lang_is_chinese():
    from backend.services.search_service import _prefix_suggestable_for_lang
    assert _prefix_suggestable_for_lang("遊戲", "zh-TW") is True


def test_suggest_terms_returns_empty_for_cjk_prefix_in_english_lang():
    """Regression: previously suggest_terms ignored lang entirely, so a CJK prefix would
    surface suggestions even in English UI mode — clicking one led nowhere, since
    search_articles_hybrid only checks the zh-TW translation when lang=zh-TW."""
    from backend.services import search_service

    db = MagicMock()

    result = search_service.suggest_terms(db, topic_id=None, prefix="遊戲", lang="en")

    assert result.suggestions == []
    db.execute.assert_not_called()  # short-circuits before touching Postgres at all


def test_suggest_terms_still_queries_redis_for_cjk_prefix_in_chinese_lang():
    from backend.services import search_service
    from shared.search_index.search_term import SearchTerm

    mock_gateway = MagicMock()
    mock_gateway.suggest.return_value = [SearchTerm(term="遊戲", occurrence_count=9)]
    with patch("shared.search_index.RedisSearchIndexGateway", return_value=mock_gateway):
        db = MagicMock()
        result = search_service.suggest_terms(db, topic_id=None, prefix="遊戲", lang="zh-TW")

    assert [s.term for s in result.suggestions] == ["遊戲"]


def test_suggest_terms_does_not_gate_non_cjk_prefix_in_chinese_lang():
    from backend.services import search_service
    from shared.search_index.search_term import SearchTerm

    mock_gateway = MagicMock()
    mock_gateway.suggest.return_value = [SearchTerm(term="learning", occurrence_count=5)]
    with patch("shared.search_index.RedisSearchIndexGateway", return_value=mock_gateway):
        db = MagicMock()
        result = search_service.suggest_terms(db, topic_id=None, prefix="lear", lang="zh-TW")

    assert [s.term for s in result.suggestions] == ["learning"]


# ---------------------------------------------------------------------------
# _find_matching_terms — Postgres autocomplete fallback (023-article-search follow-up:
# replaced the raw-SQL SqlAlchemySearchTermRepository with a direct ORM query so it can
# filter by `language` now that intelligence.search_terms splits terms by language).
# ---------------------------------------------------------------------------

def test_find_matching_terms_returns_empty_when_topic_id_none():
    from backend.services.search_service import _find_matching_terms
    db = MagicMock()

    result = _find_matching_terms(db, topic_id=None, prefix="lear", lang="en", limit=10)

    assert result == []
    db.query.assert_not_called()


def test_find_matching_terms_filters_by_topic_and_language():
    from backend.services.search_service import _find_matching_terms
    topic_id = uuid.uuid4()
    db = MagicMock()
    chain = db.query.return_value
    chain.filter.return_value = chain
    chain.order_by.return_value = chain
    chain.limit.return_value = chain
    chain.all.return_value = [MagicMock(term="learning", occurrence_count=42)]

    result = _find_matching_terms(db, topic_id=topic_id, prefix="lear", lang="zh-TW", limit=10)

    assert chain.filter.called
    assert result[0].term == "learning"
    assert result[0].occurrence_count == 42


def test_suggest_terms_postgres_fallback_uses_find_matching_terms(monkeypatch):
    from backend.services import search_service
    from shared.search_index.search_term import SearchTerm

    mock_gateway = MagicMock()
    mock_gateway.suggest.return_value = None  # Redis miss -> fall back
    monkeypatch.setattr(
        search_service, "_find_matching_terms",
        lambda db, topic_id, prefix, lang, limit: [SearchTerm(term="learning", occurrence_count=42)],
    )

    with patch("shared.search_index.RedisSearchIndexGateway", return_value=mock_gateway):
        db = MagicMock()
        result = search_service.suggest_terms(db, topic_id=uuid.uuid4(), prefix="lear", lang="en")

    assert [s.term for s in result.suggestions] == ["learning"]
    mock_gateway.repopulate.assert_called_once()
