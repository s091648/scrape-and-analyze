"""
Integration tests for /search and /search/autocomplete.

`GET /search` deliberately queries `core.articles`/`vectors.*` via raw SQL, not the
ORM (see research.md's operator-class/no-ORM-model decisions) — and raw text() SQL is
NOT rewritten by conftest.py's schema_translate_map, so it always targets the real
`core`/`vectors` schemas, never the per-test-isolated `backend_test` schema an ORM
insert (e.g. `db_session.add(Article(...))`) would land in. These fixtures therefore
seed everything via raw SQL too, so writes and this endpoint's reads agree on which
physical table they're using. Inserts still roll back with everything else at test
teardown since they share db_session's connection/transaction.

embed_query_sparse/embed_query_dense are monkeypatched to deterministic vectors
(rather than hitting a real fastembed service) so cosine-distance ordering is exact
and reproducible.

intelligence.search_terms/search_term_articles (the term->article inverted index
backing exact_match/exact_match_only — 023-article-search follow-up) are the one
exception to the raw-SQL-everywhere rule above: search_service.py queries them via the
ORM (models.SearchTerm/SearchTermArticle), which IS schema_translate_map-rewritten to
the isolated test schema, and they don't need to join against the FIXED, non-isolated
vectors.* schema the way core.articles does — so `_seed_search_term` below seeds them
via `db_session.add(...)`, not raw SQL, to land in the same (rewritten) schema that ORM
query reads.
"""
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration

_DENSE_DIM = 768
_SPARSE_DIM = 30522


def _fresh_topic(db_session) -> uuid.UUID:
    """core.articles/vectors.* are read via raw SQL (real schema, not test-isolated —
    see module docstring), so an unscoped query would match whatever real data already
    exists there. A unique topic per test keeps results deterministic."""
    topic_id = uuid.uuid4()
    db_session.execute(text(
        "INSERT INTO core.topics (id, name, display_name, is_active, tag_mode) "
        "VALUES (:id, :name, 'Test Topic', true, 'unsupervised')"
    ), {"id": topic_id, "name": f"t-{topic_id.hex[:10]}"})
    db_session.flush()
    return topic_id


def _core_article(
    db_session, topic_id, title="Machine Learning Basics", content="An article about machine learning.",
    merged_into_id=None, source="techcrunch", original_source=None, published_at=None,
) -> uuid.UUID:
    article_id = uuid.uuid4()
    db_session.execute(text(
        "INSERT INTO core.articles "
        "(id, url, url_hash, source, original_source, title, content, correlation_id, topic_id, merged_into_id, published_at) "
        "VALUES (:id, :url, :url_hash, :source, :original_source, :title, :content, :correlation_id, :topic_id, :merged_into_id, :published_at)"
    ), {
        "id": article_id, "url": f"https://example.com/{uuid.uuid4().hex}", "url_hash": uuid.uuid4().hex,
        "source": source, "original_source": original_source,
        "title": title, "content": content, "correlation_id": uuid.uuid4(),
        "topic_id": topic_id, "merged_into_id": merged_into_id, "published_at": published_at,
    })
    db_session.flush()
    return article_id


def _seed_chunk(db_session, article_id, dense_vec=None, sparse_weights=None):
    """Insert a vectors.articles + vectors.article_chunks row pointing at article_id."""
    vec_article_id = uuid.uuid4()
    db_session.execute(text(
        "INSERT INTO vectors.articles (id, url, public_article_id) "
        "VALUES (:id, :url, :public_article_id)"
    ), {"id": vec_article_id, "url": f"https://example.com/{uuid.uuid4().hex}", "public_article_id": article_id})

    dense_literal = "[" + ",".join(str(v) for v in (dense_vec or [1.0] + [0.0] * (_DENSE_DIM - 1))) + "]"
    # pgvector sparsevec indexes are 1-based (index 0 is out of bounds), unlike Python's
    # 0-based dicts — {1: 1.0} is the first dimension, not {0: 1.0}.
    weights = sparse_weights if sparse_weights is not None else {1: 1.0}
    sparse_items = ",".join(f"{k}:{v}" for k, v in weights.items())
    sparse_literal = f"{{{sparse_items}}}/{_SPARSE_DIM}"

    db_session.execute(text(
        "INSERT INTO vectors.article_chunks (article_id, chunk_index, content, dense_vector, sparse_vector) "
        "VALUES (:article_id, 0, 'chunk text', CAST(:dense AS vector), CAST(:sparse AS sparsevec))"
    ), {"article_id": vec_article_id, "dense": dense_literal, "sparse": sparse_literal})
    db_session.flush()


def _seed_search_term(db_session, topic_id, article_id, term, language="en", occurrence_count=1):
    """Seeds one intelligence.search_terms row (or reuses one already inserted for the
    same topic/term/language within this test) plus a search_term_articles link, as
    RebuildSearchIndexUseCase would have built them.

    ORM (db_session.add(...)), not raw SQL — the opposite of _core_article/_seed_chunk
    above. Unlike core.articles/vectors.article_chunks (module docstring: raw SQL there
    to bypass conftest.py's schema_translate_map and hit the real schema, since
    vectors.article_chunks is a FIXED, non-isolated schema that must join against the
    same real core.articles row), intelligence.search_terms/search_term_articles are
    both ordinary per-test-isolated DDD schemas with no such join constraint — and
    backend/services/search_service.py's _exact_match_article_ids/_find_matching_terms
    query them via the ORM (models.SearchTerm/SearchTermArticle), which IS
    schema_translate_map-rewritten. Seeding via raw SQL here would land in the real
    `intelligence` schema and never be seen by that ORM query in this test harness.

    search_term_articles.article_id FKs to core.articles.id, itself translated to the
    isolated test schema for this ORM insert — but _core_article() above seeds the REAL
    core.articles via raw SQL (needed for vectors.article_chunks' join), so that FK's
    actual target row wouldn't exist in the test schema without also creating a minimal,
    same-id ORM Article row here purely to satisfy the constraint (harmless duplication:
    production only ever has the one real core.articles)."""
    from models.article import Article
    from models.search_term import SearchTerm
    from models.search_term_article import SearchTermArticle

    if db_session.get(Article, article_id) is None:
        # topic_id deliberately omitted (nullable on Article) — backend_test.topics has
        # no matching row for `topic_id` either (_fresh_topic seeds the REAL core.topics
        # via raw SQL, same as _core_article), and this stub row only needs to satisfy
        # search_term_articles' article_id FK, not carry a real topic association.
        db_session.add(Article(
            id=article_id, url=f"https://example.com/{article_id}", url_hash=article_id.hex,
            source="techcrunch", title="seed", content="seed", correlation_id=uuid.uuid4(),
        ))
        db_session.flush()

    existing = (
        db_session.query(SearchTerm)
        .filter_by(topic_id=topic_id, term=term, language=language)
        .first()
    )
    if existing is None:
        existing = SearchTerm(topic_id=topic_id, term=term, language=language, occurrence_count=occurrence_count)
        db_session.add(existing)
        db_session.flush()
    db_session.add(SearchTermArticle(search_term_id=existing.id, article_id=article_id))
    db_session.flush()


def _patch_embeddings(monkeypatch, dense_vec=None, sparse_weights=None):
    """embed_query is async (023-article-search follow-up: it now calls chatbot_plugin_sdk
    provider .embed() coroutines instead of a sync fastembed HTTP call), so the stand-in
    must be an async function too — a plain lambda returning a tuple can't be awaited."""
    from backend.services import search_service
    resolved_sparse = sparse_weights or {1: 1.0}
    resolved_dense = dense_vec or [1.0] + [0.0] * (_DENSE_DIM - 1)

    async def _fake_embed_query(q):
        return resolved_sparse, resolved_dense

    monkeypatch.setattr(search_service, "embed_query", _fake_embed_query)


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------

def test_search_matching_query_returns_the_article(api_client, db_session, monkeypatch):
    topic_id = _fresh_topic(db_session)
    article_id = _core_article(db_session, topic_id)
    _seed_chunk(db_session, article_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(article_id)


def test_search_no_match_returns_empty_not_error(api_client, db_session, monkeypatch):
    _patch_embeddings(monkeypatch)
    # Fresh random topic with no seeded chunks at all
    r = api_client.get(f"/search?q=nonexistent&topic_id={uuid.uuid4()}")

    assert r.status_code == 200
    data = r.json()
    assert data == {"items": [], "total": 0, "page": 1, "size": 20}


def test_search_empty_query_returns_400(api_client):
    r = api_client.get("/search?q=")
    assert r.status_code == 400


def test_search_whitespace_only_query_returns_400(api_client):
    r = api_client.get("/search?q=%20%20")
    assert r.status_code == 400


def test_search_missing_token_returns_401(api_client):
    r = api_client.app_client.get("/search?q=test", headers={"Authorization": ""})
    assert r.status_code == 401


def test_search_respects_topic_id(api_client, db_session, monkeypatch):
    topic_a = _fresh_topic(db_session)
    topic_b = _fresh_topic(db_session)
    article_id = _core_article(db_session, topic_a)
    _seed_chunk(db_session, article_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=machine%20learning&topic_id={topic_b}")

    assert r.status_code == 200
    assert r.json()["total"] == 0  # article belongs to topic_a, not topic_b


def test_search_excludes_tombstoned_articles(api_client, db_session, monkeypatch):
    topic_id = _fresh_topic(db_session)
    # survivor's content deliberately does NOT contain "machine learning" (unlike
    # _core_article's default) — this test isolates "the tombstoned loser must not
    # appear," not "no article in this topic may match," and the survivor sharing the
    # query term via _core_article's default content would otherwise legitimately
    # surface it too (it's the real, non-tombstoned article).
    survivor_id = _core_article(db_session, topic_id, title="Survivor", content="unrelated survivor content")
    loser_id = _core_article(db_session, topic_id, title="Loser", merged_into_id=survivor_id)
    _seed_chunk(db_session, loser_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}")

    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_search_lang_returns_translated_fields_and_exact_match_from_inverted_index(api_client, db_session, monkeypatch):
    """Regression: a non-English query can only ever literally match the translated text,
    never core.articles' English original — translated_title/content still come from
    core.articles_translation (raw SQL, seeded via raw SQL to match), while exact_match
    now comes from the term->article inverted index (intelligence.search_terms/
    search_term_articles — 023-article-search follow-up), seeded via _seed_search_term
    with language='zh-TW' so the lang-scoped lookup finds it.

    Seeds every token tokenize("機器學習") actually produces (rather than assuming the
    whole 4-char string is one token) — jieba may segment it into "機器"+"學習" depending
    on dict version (see shared/search_index/tokenizer.py's own test caveat), and
    _exact_match_article_ids requires ALL of the query's tokens to be linked, so seeding
    fewer than the real tokenizer produces would make this test flaky/wrong regardless of
    which way jieba happens to split it."""
    from shared.search_index.tokenizer import tokenize

    topic_id = _fresh_topic(db_session)
    article_id = _core_article(db_session, topic_id, title="Machine Learning Basics", content="An article about machine learning.")
    _seed_chunk(db_session, article_id)
    db_session.execute(text(
        "INSERT INTO core.articles_translation (id, article_id, language, title, content) "
        "VALUES (gen_random_uuid(), :article_id, 'zh-TW', :title, :content)"
    ), {"article_id": article_id, "title": "機器學習基礎", "content": "一篇關於機器學習的文章。"})
    db_session.flush()
    for token in tokenize("機器學習"):
        _seed_search_term(db_session, topic_id, article_id, token, language="zh-TW")
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=%E6%A9%9F%E5%99%A8%E5%AD%B8%E7%BF%92&topic_id={topic_id}&lang=zh-TW")  # q=機器學習

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["translated_title"] == "機器學習基礎"
    assert item["translated_content"] == "一篇關於機器學習的文章。"
    assert item["exact_match"] is True


def test_search_exact_match_flag_false_when_not_in_inverted_index(api_client, db_session, monkeypatch):
    """A semantic-only RRF neighbor (no intelligence.search_term_articles link for the
    query's tokens) must come back exact_match=False, not raise or default to True."""
    topic_id = _fresh_topic(db_session)
    article_id = _core_article(db_session, topic_id, title="Unrelated Semantic Neighbor", content="something else entirely")
    _seed_chunk(db_session, article_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=cyberattacks&topic_id={topic_id}")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["exact_match"] is False


def test_search_aggregator_filter_excludes_non_matching_source(api_client, db_session, monkeypatch):
    """023-article-search follow-up regression: GET /search silently ignored every
    filter param the frontend sends while a search is active — this exercises the real
    HTTP path end to end, not just the mocked service-layer unit tests."""
    topic_id = _fresh_topic(db_session)
    match_id = _core_article(db_session, topic_id, source="techcrunch")
    _seed_chunk(db_session, match_id)
    other_id = _core_article(db_session, topic_id, title="Machine Learning Basics", content="An article about machine learning.", source="arxiv")
    _seed_chunk(db_session, other_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}&aggregator=techcrunch")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(match_id)


def test_search_published_after_filter_excludes_older_articles(api_client, db_session, monkeypatch):
    import datetime
    topic_id = _fresh_topic(db_session)
    recent_id = _core_article(db_session, topic_id, published_at=datetime.date(2026, 6, 1))
    _seed_chunk(db_session, recent_id)
    old_id = _core_article(db_session, topic_id, title="Machine Learning Basics", content="An article about machine learning.", published_at=datetime.date(2020, 1, 1))
    _seed_chunk(db_session, old_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}&published_after=2025-01-01")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(recent_id)


def test_search_sort_overrides_default_rrf_relevance_order(api_client, db_session, monkeypatch):
    """Without `sort`, the closer-vector article ranks first (pure RRF relevance) — with
    `sort=published_at&order=desc`, the newer article must rank first instead, even though
    it's the worse semantic match."""
    import datetime
    topic_id = _fresh_topic(db_session)
    closer_but_older_id = _core_article(db_session, topic_id, title="A", published_at=datetime.date(2020, 1, 1))
    _seed_chunk(db_session, closer_but_older_id, dense_vec=[1.0] + [0.0] * (_DENSE_DIM - 1))
    farther_but_newer_id = _core_article(db_session, topic_id, title="B", content="An article about machine learning.", published_at=datetime.date(2026, 1, 1))
    _seed_chunk(db_session, farther_but_newer_id, dense_vec=[0.0, 1.0] + [0.0] * (_DENSE_DIM - 2))
    # Query vector matches closer_but_older_id exactly — without a sort override it must
    # win on relevance despite being the older article.
    _patch_embeddings(monkeypatch, dense_vec=[1.0] + [0.0] * (_DENSE_DIM - 1))

    default_order = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}")
    assert default_order.json()["items"][0]["id"] == str(closer_but_older_id)

    sorted_by_date = api_client.get(f"/search?q=machine%20learning&topic_id={topic_id}&sort=published_at&order=desc")
    assert sorted_by_date.json()["items"][0]["id"] == str(farther_but_newer_id)


def test_search_exact_match_only_respects_aggregator_filter(api_client, db_session, monkeypatch):
    topic_id = _fresh_topic(db_session)
    match_id = _core_article(db_session, topic_id, title="Cyberattacks Explained", content="an article about cyberattacks", source="techcrunch")
    _seed_search_term(db_session, topic_id, match_id, "cyberattacks")
    other_id = _core_article(db_session, topic_id, title="Cyberattacks Elsewhere", content="an article about cyberattacks", source="arxiv")
    _seed_search_term(db_session, topic_id, other_id, "cyberattacks")
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=cyberattacks&topic_id={topic_id}&exact_match_only=true&aggregator=techcrunch")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(match_id)


def test_search_exact_match_only_uses_inverted_index_not_rrf(api_client, db_session, monkeypatch):
    """Regression: exact_match_only=True is a fully separate retrieval path over the
    term->article inverted index (023-article-search follow-up) — it must find an exact
    match even when that article has NO vectors.article_chunks row at all (so RRF could
    never have surfaced it), and must exclude an RRF-only semantic neighbor that has no
    inverted-index link for the query's tokens."""
    topic_id = _fresh_topic(db_session)
    exact_id = _core_article(db_session, topic_id, title="Cyberattacks Explained", content="an article about cyberattacks")
    _seed_search_term(db_session, topic_id, exact_id, "cyberattacks")
    # Deliberately no _seed_chunk(exact_id) — proves this path doesn't depend on RRF/vectors.
    semantic_id = _core_article(db_session, topic_id, title="Unrelated Semantic Neighbor", content="something else entirely")
    _seed_chunk(db_session, semantic_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=cyberattacks&topic_id={topic_id}&exact_match_only=true")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [str(exact_id)]
    assert data["items"][0]["exact_match"] is True


def test_search_exact_match_only_requires_all_query_tokens_and_semantics(api_client, db_session, monkeypatch):
    """AND (intersection), not OR (union), across a multi-token query's tokens — user-
    confirmed design decision (023-article-search follow-up): an article containing only
    one of the two tokens must not match; hybrid RRF search is relied on to surface
    articles that are merely related, not this exact-match path."""
    topic_id = _fresh_topic(db_session)
    both_id = _core_article(db_session, topic_id, title="Cyberattacks on Critical Infrastructure")
    _seed_search_term(db_session, topic_id, both_id, "cyberattacks")
    _seed_search_term(db_session, topic_id, both_id, "infrastructure")
    only_one_id = _core_article(db_session, topic_id, title="Cyberattacks on Retailers")
    _seed_search_term(db_session, topic_id, only_one_id, "cyberattacks")
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=cyberattacks%20infrastructure&topic_id={topic_id}&exact_match_only=true")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [str(both_id)]


def test_search_exact_match_only_updates_total_for_correct_pagination(api_client, db_session, monkeypatch):
    """Regression: total (and therefore the frontend's pagination) must reflect the
    inverted-index-matched count, not any unfiltered candidate set — a client-side
    per-page filter would leave totalPages computed from the wrong total, so later pages
    could show zero results despite pagination claiming more existed."""
    topic_id = _fresh_topic(db_session)
    exact_id = _core_article(db_session, topic_id, title="Cyberattacks Explained")
    _seed_search_term(db_session, topic_id, exact_id, "cyberattacks")
    for _ in range(7):
        semantic_id = _core_article(db_session, topic_id, title="Unrelated Semantic Neighbor")
        _seed_chunk(db_session, semantic_id)
    _patch_embeddings(monkeypatch)

    r = api_client.get(f"/search?q=cyberattacks&topic_id={topic_id}&exact_match_only=true")

    assert r.status_code == 200
    assert r.json()["total"] == 1  # not 8 — the semantic-only neighbors never linked "cyberattacks"


# ---------------------------------------------------------------------------
# GET /search/autocomplete
# ---------------------------------------------------------------------------

def _search_index_redis_url() -> str:
    import os
    return os.environ.get("SEARCH_INDEX_REDIS_URL", "redis://redis:6379/2")


# Note: unlike db_session's Postgres writes, gateway.rebuild() calls below write to the
# real dev Redis instance directly (no transactional rollback net — Redis isn't part of
# the Postgres transaction). Each test uses a fresh random topic_id to avoid collisions;
# the small amount of leftover test data in a local dev Redis DB is an accepted, low-
# stakes tradeoff rather than building bespoke per-test Redis cleanup.


def test_autocomplete_returns_ranked_suggestions_from_a_populated_index(api_client):
    from shared.search_index import RedisSearchIndexGateway
    topic_id = uuid.uuid4()
    gateway = RedisSearchIndexGateway(redis_url=_search_index_redis_url())
    gateway.rebuild({topic_id: {"learning": 42, "learned": 7}})

    r = api_client.get(f"/search/autocomplete?prefix=lear&topic_id={topic_id}")

    assert r.status_code == 200
    terms = [s["term"] for s in r.json()["suggestions"]]
    assert terms == ["learning", "learned"]  # ranked by occurrence_count desc


def test_autocomplete_returns_empty_for_cjk_prefix_when_lang_not_chinese(api_client):
    """Regression: a CJK prefix must not be suggested in a non-Chinese UI locale, since
    GET /search's translation lookup (the only way a CJK query can ever literally match
    anything) is itself gated on lang — suggesting one anyway leads to a dead-end search."""
    from shared.search_index import RedisSearchIndexGateway
    topic_id = uuid.uuid4()
    gateway = RedisSearchIndexGateway(redis_url=_search_index_redis_url())
    gateway.rebuild({topic_id: {"遊戲": 9, "遊戲化": 3}})

    r = api_client.get(f"/search/autocomplete?prefix=遊戲&topic_id={topic_id}&lang=en")

    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_autocomplete_returns_cjk_suggestions_when_lang_is_chinese(api_client):
    from shared.search_index import RedisSearchIndexGateway
    topic_id = uuid.uuid4()
    gateway = RedisSearchIndexGateway(redis_url=_search_index_redis_url())
    gateway.rebuild({topic_id: {"遊戲": 9, "遊戲化": 3}})

    r = api_client.get(f"/search/autocomplete?prefix=遊戲&topic_id={topic_id}&lang=zh-TW")

    assert r.status_code == 200
    terms = [s["term"] for s in r.json()["suggestions"]]
    assert terms == ["遊戲", "遊戲化"]


def test_autocomplete_matches_anywhere_in_term_not_just_prefix(api_client):
    from shared.search_index import RedisSearchIndexGateway
    topic_id = uuid.uuid4()
    gateway = RedisSearchIndexGateway(redis_url=_search_index_redis_url())
    gateway.rebuild({topic_id: {"learning": 10}})

    r = api_client.get(f"/search/autocomplete?prefix=arn&topic_id={topic_id}")  # "arn" is inside "learning", not a prefix

    assert r.status_code == 200
    assert [s["term"] for s in r.json()["suggestions"]] == ["learning"]


def test_autocomplete_falls_back_to_postgres_when_redis_index_never_built(api_client, db_session):
    # A fresh random topic that RedisSearchIndexGateway.rebuild() has never touched —
    # this exact (topic_id, prefix) ZSET key is absent, so this must degrade to the
    # Postgres fallback (which is also empty here) rather than erroring.
    topic_id = uuid.uuid4()
    r = api_client.get(f"/search/autocomplete?prefix=lear&topic_id={topic_id}")

    assert r.status_code == 200
    assert r.json() == {"suggestions": []}


def test_autocomplete_falls_back_to_postgres_when_redis_unavailable(api_client, db_session, monkeypatch):
    from shared.search_index.redis_gateway import RedisSearchIndexGateway

    topic_id = uuid.uuid4()
    article_id = uuid.uuid4()
    _seed_search_term(db_session, topic_id, article_id, "learning", occurrence_count=42)

    monkeypatch.setattr(RedisSearchIndexGateway, "suggest", lambda self, topic_id, prefix, limit=10: None)

    r = api_client.get(f"/search/autocomplete?prefix=lear&topic_id={topic_id}")

    assert r.status_code == 200
    assert r.json()["suggestions"] == [{"term": "learning", "occurrence_count": 42}]


def test_autocomplete_empty_prefix_returns_400(api_client):
    r = api_client.get("/search/autocomplete?prefix=")
    assert r.status_code == 400


def test_autocomplete_missing_token_returns_401(api_client):
    r = api_client.app_client.get("/search/autocomplete?prefix=lear", headers={"Authorization": ""})
    assert r.status_code == 401


def test_autocomplete_redis_hit_latency_within_ceiling(api_client):
    """FR-011/SC-002: p95 < 300ms, target < 100ms, on the Redis-hit path (no fastembed/
    Postgres round-trip involved in autocomplete at all). Measured via FastAPI's
    in-process TestClient, which has no real network/TLS overhead unlike production — this
    is a repeatable regression guard against an accidental O(n) scan replacing the O(log N)
    ZREVRANGE lookup, not a substitute for a real production latency measurement."""
    import time
    from shared.search_index import RedisSearchIndexGateway

    topic_id = uuid.uuid4()
    gateway = RedisSearchIndexGateway(redis_url=_search_index_redis_url())
    gateway.rebuild({topic_id: {f"term{i}": i for i in range(50)}})  # realistic-ish fan-out

    durations_ms = []
    for _ in range(20):
        start = time.perf_counter()
        r = api_client.get(f"/search/autocomplete?prefix=term&topic_id={topic_id}")
        durations_ms.append((time.perf_counter() - start) * 1000)
        assert r.status_code == 200

    durations_ms.sort()
    p95 = durations_ms[int(len(durations_ms) * 0.95)]
    assert p95 < 300, f"autocomplete p95 latency {p95:.1f}ms exceeds the 300ms ceiling (FR-011)"
