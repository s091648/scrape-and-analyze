import asyncio
import functools
import logging
import os
import re
from datetime import date
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session

from shared.domain.exceptions import ExternalDependencyError
from shared.search_index.tokenizer import tokenize
from backend.config import (
    SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN,
    RAG_DENSE_PROVIDER, RAG_DENSE_MODEL, RAG_DENSE_DIMENSION, RAG_DENSE_API_KEY_ENV,
    RAG_DENSE_ENDPOINT_URL, RAG_DENSE_RPM, RAG_DENSE_TPM, RAG_DENSE_RPD, RAG_DENSE_SPLIT_BATCH_ON_TPM,
    RAG_SPARSE_PROVIDER, RAG_SPARSE_MODEL, RAG_SPARSE_DIMENSION, RAG_SPARSE_ENDPOINT_URL,
    RAG_SPARSE_RPM, RAG_SPARSE_TPM, RAG_SPARSE_RPD, RAG_SPARSE_TIMEOUT,
)
from backend.schemas.article import ArticleOut, PaginatedArticles
from backend.schemas.search import AutocompleteResponse, SearchSuggestion

logger = logging.getLogger(__name__)
event_logger = structlog.get_logger(__name__)

_CANDIDATE_MULTIPLIER = 3  # top_k * 3 candidates per source, headroom for RRF re-ranking
_RRF_K = 60


def _build_dense_provider():
    from chatbot_plugin_sdk import build_dense_provider
    if not RAG_DENSE_PROVIDER:
        return None
    return build_dense_provider({
        "provider_type": RAG_DENSE_PROVIDER,
        "model": RAG_DENSE_MODEL,
        "dimension": RAG_DENSE_DIMENSION,
        "api_key": os.environ.get(RAG_DENSE_API_KEY_ENV, "") if RAG_DENSE_API_KEY_ENV else "",
        "endpoint_url": RAG_DENSE_ENDPOINT_URL,
        "rpm": RAG_DENSE_RPM,
        "tpm": RAG_DENSE_TPM,
        "rpd": RAG_DENSE_RPD,
        "split_batch_on_tpm": RAG_DENSE_SPLIT_BATCH_ON_TPM,
    })


def _build_sparse_provider():
    from chatbot_plugin_sdk import build_sparse_provider
    if not RAG_SPARSE_PROVIDER:
        return None
    return build_sparse_provider({
        "provider_type": RAG_SPARSE_PROVIDER,
        "model": RAG_SPARSE_MODEL,
        "dimension": RAG_SPARSE_DIMENSION,
        "endpoint_url": RAG_SPARSE_ENDPOINT_URL,
        "rpm": RAG_SPARSE_RPM,
        "tpm": RAG_SPARSE_TPM,
        "rpd": RAG_SPARSE_RPD,
        "timeout": RAG_SPARSE_TIMEOUT,
    })


async def embed_query(query: str) -> tuple[Optional[dict], Optional[list[float]]]:
    """Embeds the visitor's search string into `(sparse_weights, dense_vector)` via
    chatbot_plugin_sdk's provider classes (GeminiDenseProvider / EndpointProvider,
    picked by `build_dense_provider`/`build_sparse_provider` from the RAG_DENSE_*/
    RAG_SPARSE_* config in backend/config.py) — the exact same providers and config
    src/'s RAG ingestion pipeline (src/bootstrap.py::build_collection_pipeline) uses to
    embed articles into vectors.article_chunks. This is required, not a style choice: a
    query embedded by a different model/provider than the one that embedded the stored
    article vectors would land in a different vector space, making cosine distance
    between them meaningless (023-article-search follow-up — this replaced an earlier
    version that called the shared fastembed service directly for both sparse+dense,
    which left dense silently `None` since fastembed's EMBED_DENSE_MODEL was never
    configured, so /search ran sparse-only on an English-only SPLADE model with no
    meaningful signal for CJK queries).

    Either half of the returned tuple is `None` when that provider isn't configured
    (RAG_DENSE_PROVIDER/RAG_SPARSE_PROVIDER empty) — callers must handle a `None` for
    either return value, same contract as before."""
    dense_provider = _build_dense_provider()
    sparse_provider = _build_sparse_provider()

    async def _embed_or_none(provider):
        if provider is None:
            return None
        return await provider.embed([query])

    dense_result, sparse_result = await asyncio.gather(
        _embed_or_none(dense_provider), _embed_or_none(sparse_provider),
    )
    dense = dense_result[0] if dense_result else None
    sparse = sparse_result[0] if sparse_result else None
    return sparse, dense


def _sparse_vec_literal(weights: dict, dim: int = 30522) -> str:
    """{index: weight} -> pgvector SPARSEVEC wire format: '{0:0.5,1:0.3}/30522'."""
    items = ",".join(f"{int(k)}:{v}" for k, v in sorted(weights.items(), key=lambda x: int(x[0])) if v != 0)
    return f"{{{items}}}/{dim}"


def _dense_vec_literal(values: list[float]) -> str:
    """[v1, v2, ...] -> pgvector VECTOR wire format: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(v) for v in values) + "]"


_BASE_QUERY = """
    SELECT a.id, a.url, a.source, a.title, a.content, a.published_at, a.scraped_at,
           MIN(ac.{column} {op} CAST(:query_vec AS {cast})) AS best_distance
    FROM vectors.article_chunks ac
    JOIN vectors.articles va ON ac.article_id = va.id
    JOIN core.articles a ON a.id = va.public_article_id
    WHERE ac.{column} IS NOT NULL
      AND a.merged_into_id IS NULL
      {topic_filter}
      {id_filter}
    GROUP BY a.id, a.url, a.source, a.title, a.content, a.published_at, a.scraped_at
    ORDER BY best_distance
    LIMIT :candidate_k
"""


def _run_vector_query(
    db: Session, column: str, cast: str, query_vec: str, topic_id: Optional[UUID], candidate_k: int,
    filtered_ids: Optional[set] = None,
):
    """`filtered_ids` (from `_filtered_article_ids`) narrows the candidate pool to articles
    matching the aggregator/original_source/tag/tag_group/date-range filters *before*
    vector ranking/LIMIT — same reasoning as `topic_filter`: applying a filter after RRF
    merge (a post-hoc filter on already-limited candidates) could disagree with total/
    pagination the same way `exact_match_only` deliberately avoids (see that flag's own
    docstring). `None` (the default) means "no filter requested" and omits the clause
    entirely — zero behavior change for every existing caller."""
    topic_filter = "AND a.topic_id = :topic_id" if topic_id is not None else ""
    id_filter = "AND a.id IN :filtered_ids" if filtered_ids is not None else ""
    sql = _BASE_QUERY.format(column=column, op="<=>", cast=cast, topic_filter=topic_filter, id_filter=id_filter)
    stmt = text(sql)
    params = {"query_vec": query_vec, "candidate_k": candidate_k}
    if topic_id is not None:
        params["topic_id"] = str(topic_id)
    if filtered_ids is not None:
        stmt = stmt.bindparams(bindparam("filtered_ids", expanding=True))
        params["filtered_ids"] = list(filtered_ids)
    return db.execute(stmt, params).mappings().all()


def _rrf_merge(dense_rows, sparse_rows, k: int = _RRF_K) -> list[tuple]:
    """Reciprocal Rank Fusion of two ranked result sets, keyed by article id.

    Score for each article: sum(1 / (k + rank + 1)) across both lists — higher score
    means it ranked well in more lists. Only cares about rank position, never the raw
    distance value, so dense (cosine) and sparse (cosine) results merge without needing
    to normalize across the two — see specs/023-article-search/research.md.
    """
    scores: dict = {}
    rows: dict = {}

    for rank, row in enumerate(dense_rows):
        key = row["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        rows[key] = row

    for rank, row in enumerate(sparse_rows):
        key = row["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        rows.setdefault(key, row)  # prefer the dense row's field values when both have it

    ordered = sorted(scores, key=lambda article_id: scores[article_id], reverse=True)
    return [(rows[article_id], scores[article_id]) for article_id in ordered]


def _filtered_article_ids(
    db: Session,
    topic_id: Optional[UUID],
    aggregators: Optional[list],
    original_sources: Optional[list],
    tags: Optional[list],
    tag_groups: Optional[list],
    published_after: Optional[date],
    published_before: Optional[date],
    scraped_after: Optional[date],
    scraped_before: Optional[date],
) -> Optional[set]:
    """The search endpoint's counterpart to `get_articles_paginated`'s (backend/services/
    article_service.py) filter-building block — same filter semantics (`aggregators`
    filters `Article.source`, `original_sources` filters `Article.original_source`,
    `tags`/`tag_groups` via the article_tags join table), reused here rather than shared
    directly since that function also handles pagination/sorting/favorites this endpoint
    doesn't need.

    Returns `None` (not an empty set) when no filter arg is given at all — "no filter
    requested," distinct from "filters given but nothing matched" (empty set) — callers
    must treat `None` as "don't restrict the candidate pool," the same convention
    `_exact_match_article_ids` already uses. This also avoids `_run_vector_query` adding a
    pointless `id IN (...)` clause (with every article's UUID as a bind param) to the
    overwhelmingly common case of a search with no filters active at all.

    Raw SQL against `core.articles`/`intelligence.article_tags`/`intelligence.tags`/
    `intelligence.tag_group_definitions` — matches this file's real-schema convention for
    every other `core.articles`/`vectors.*` query (see this module's own top-level design
    docstrings and backend/tests/integration/test_search.py's module docstring): raw
    text() SQL is NOT rewritten by conftest.py's schema_translate_map, so, like
    `_run_vector_query`/`_fetch_articles_by_ids`, this always targets the same real
    `core.articles` rows those do. An ORM query here (`models.Article`) WOULD be rewritten
    to the isolated test schema and silently miss the raw-SQL-seeded rows those functions
    read, unlike `_exact_match_article_ids`'s ORM query, whose only inputs
    (intelligence.search_terms/search_term_articles) don't have that constraint."""
    if not any([
        aggregators, original_sources, tags, tag_groups,
        published_after, published_before, scraped_after, scraped_before,
    ]):
        return None

    conditions = ["a.merged_into_id IS NULL"]
    params: dict = {}
    expanding_params: list = []

    if topic_id is not None:
        conditions.append("a.topic_id = :topic_id")
        params["topic_id"] = str(topic_id)
    if aggregators:
        conditions.append("a.source IN :aggregators")
        params["aggregators"] = list(aggregators)
        expanding_params.append("aggregators")
    if original_sources:
        conditions.append("a.original_source IN :original_sources")
        params["original_sources"] = list(original_sources)
        expanding_params.append("original_sources")
    if published_after:
        conditions.append("a.published_at >= :published_after")
        params["published_after"] = published_after
    if published_before:
        conditions.append("a.published_at <= :published_before")
        params["published_before"] = published_before
    if scraped_after:
        conditions.append("a.scraped_at >= :scraped_after")
        params["scraped_after"] = scraped_after
    if scraped_before:
        conditions.append("a.scraped_at <= :scraped_before")
        params["scraped_before"] = scraped_before
    # AND-intersection (an article must have every listed tag/tag_group), matching
    # get_articles_paginated's own per-tag filter loop — one EXISTS clause per name.
    for i, tag_name in enumerate(tags or []):
        key = f"tag_{i}"
        conditions.append(
            "EXISTS (SELECT 1 FROM intelligence.article_tags iat "
            "JOIN intelligence.tags it ON it.id = iat.tag_id "
            f"WHERE iat.article_id = a.id AND it.name = :{key})"
        )
        params[key] = tag_name
    for i, group_name in enumerate(tag_groups or []):
        key = f"tag_group_{i}"
        conditions.append(
            "EXISTS (SELECT 1 FROM intelligence.article_tags iat "
            "JOIN intelligence.tags it ON it.id = iat.tag_id "
            "JOIN intelligence.tag_group_definitions itg ON itg.id = it.tag_group_id "
            f"WHERE iat.article_id = a.id AND itg.name = :{key})"
        )
        params[key] = group_name

    sql = "SELECT a.id FROM core.articles a WHERE " + " AND ".join(conditions)
    stmt = text(sql)
    if expanding_params:
        stmt = stmt.bindparams(*(bindparam(name, expanding=True) for name in expanding_params))
    return {row["id"] for row in db.execute(stmt, params).mappings().all()}


# Fields available on both the RRF path's rows (_BASE_QUERY's SELECT) and the exact-match
# path's rows (_fetch_articles_by_ids' SELECT) — an explicit `sort` naming anything else
# (view_count, a catalog metric_key) has no column to reorder by here and is left a no-op,
# the same graceful degradation article_service.py's own unrecognized-sort fallback uses.
_SORTABLE_ROW_FIELDS = {"published_at", "scraped_at", "source", "title"}


def _reorder_by_field(items: list, sort: Optional[str], order: str, key_fn) -> list:
    """Re-orders an already-fetched, already-paginatable result list by `sort`/`order` —
    used to let an explicit sort selection override a search result's default ordering
    (RRF relevance for the hybrid path, newest-first for the exact-match path). `sort=None`
    (no explicit choice — the frontend only sends `sort` when the visitor picked one, see
    frontend/lib/api/search.ts) or a `sort` not in `_SORTABLE_ROW_FIELDS` leaves `items`
    untouched.

    `None` values sort last regardless of `order` — mirrors `get_articles_paginated`'s own
    `nullslast()` for exactly the same reason (Postgres defaults to NULLS FIRST on DESC,
    which would otherwise float every article missing this field to the top). Implemented
    as an explicit comparator (not a `(value is None, value)` sort key) so it never risks
    comparing `None` against a real value or against a mismatched-type placeholder."""
    if not sort or sort not in _SORTABLE_ROW_FIELDS:
        return items
    descending = order != "asc"

    def _cmp(a, b):
        va, vb = key_fn(a), key_fn(b)
        if va is None and vb is None:
            return 0
        if va is None:
            return 1
        if vb is None:
            return -1
        if va == vb:
            return 0
        if descending:
            return -1 if va > vb else 1
        return -1 if va < vb else 1

    return sorted(items, key=functools.cmp_to_key(_cmp))


def _exact_match_article_ids(db: Session, query: str, topic_id: Optional[UUID], lang: str) -> Optional[set]:
    """AND-intersection of every query token's article set, via the term->article
    inverted index (intelligence.search_terms + intelligence.search_term_articles —
    023-article-search follow-up). Independent of RRF/vector retrieval's candidate_k
    bound entirely — this is `exact_match_only`'s sole candidate source, and also what
    every RRF result's per-item `exact_match` flag is checked against (replacing an
    earlier plain substring `_is_exact_match` check: that approach could disagree with
    autocomplete's occurrence_count whenever jieba's tokenizer folded a query into a
    larger compound term, e.g. "遊戲" vs "遊戲化" — using the exact same tokenize() +
    inverted index both autocomplete and this now share closes that gap by construction).

    `query` is tokenized with the identical algorithm RebuildSearchIndexUseCase used to
    build the index — a token that doesn't match how the corresponding article text was
    tokenized at index-build time can never be found here, by design (same reasoning as
    autocomplete's occurrence_count). `lang` scopes which language's terms are searched:
    "en" only ever matches original-language text, anything else only ever matches that
    language's ArticleTranslation — mirrors every other lang-aware endpoint's convention.

    Returns `None` when `query` tokenizes to nothing (e.g. entirely stopwords/too-short
    tokens) or `topic_id` isn't resolvable — callers must treat that as "no signal",
    distinct from an empty set ("tokenized fine, but no single article contains every
    token"). Returns a `set[UUID]` of article_ids otherwise."""
    from models.search_term import SearchTerm as SearchTermModel
    from models.search_term_article import SearchTermArticle

    tokens = tokenize(query)
    if not tokens:
        return None

    q = (
        db.query(SearchTermArticle.article_id)
        .join(SearchTermModel, SearchTermModel.id == SearchTermArticle.search_term_id)
        .filter(SearchTermModel.language == lang, SearchTermModel.term.in_(tokens))
    )
    if topic_id is not None:
        q = q.filter(SearchTermModel.topic_id == topic_id)
    q = (
        q.group_by(SearchTermArticle.article_id)
        .having(func.count(func.distinct(SearchTermModel.term)) == len(tokens))
    )
    return {row.article_id for row in q.all()}


def _fetch_articles_by_ids(db: Session, article_ids: set, topic_id: Optional[UUID]) -> list:
    """Full article rows for `exact_match_only`'s candidate pool, newest-first. Raw SQL
    against core.articles, not the ORM — matches this file's existing convention for
    every other core.articles/vectors.* query (see backend/tests/integration/
    test_search.py's module docstring: an ORM query here would be schema_translate_map-
    rewritten to the isolated test schema in the integration test harness, while
    intelligence.search_terms/search_term_articles' rows — this function's only input —
    correctly go through that same translation, so mixing the two would silently see two
    different `core.articles`/`intelligence.search_terms` in tests even though there's
    only one of each in production).

    Re-checks `merged_into_id IS NULL`/`topic_id` at request time (not just relying on
    RebuildSearchIndexUseCase's own filtering) — the inverted index is rebuilt at most
    once a day, so an article tombstoned since the last rebuild would otherwise still
    surface here until the next cycle, same staleness guard `_BASE_QUERY` already applies
    to the RRF path."""
    if not article_ids:
        return []
    topic_filter = "AND topic_id = :topic_id" if topic_id is not None else ""
    sql = (
        "SELECT id, url, source, title, content, published_at, scraped_at "
        "FROM core.articles "
        "WHERE id IN :article_ids AND merged_into_id IS NULL "
        f"{topic_filter} "
        "ORDER BY published_at DESC NULLS LAST"
    )
    params = {"article_ids": list(article_ids)}
    if topic_id is not None:
        params["topic_id"] = str(topic_id)
    return db.execute(
        text(sql).bindparams(bindparam("article_ids", expanding=True)), params,
    ).mappings().all()


def _fetch_translations(db: Session, article_ids: list[str], lang: str) -> dict:
    """article_id (str) -> {"title", "content"} for every core.articles_translation row
    matching `lang` among `article_ids`. Raw SQL, not the ORM — matches this file's
    existing convention (every other query here is raw SQL against the real core/vectors
    schema; see backend/tests/integration/test_search.py's module docstring) rather than
    introducing the only ORM query in an otherwise fully-raw-SQL request path."""
    if not article_ids:
        return {}
    rows = db.execute(
        text(
            "SELECT article_id, title, content FROM core.articles_translation "
            "WHERE article_id IN :article_ids AND language = :lang"
        ).bindparams(bindparam("article_ids", expanding=True)),
        {"article_ids": article_ids, "lang": lang},
    ).mappings().all()
    return {str(row["article_id"]): row for row in rows}


def _search_exact_match_only(
    db: Session, query: str, topic_id: Optional[UUID], page: int, size: int, lang: str,
    filtered_ids: Optional[set] = None, sort: Optional[str] = None, order: str = "desc",
) -> PaginatedArticles:
    """`exact_match_only=True`'s entire retrieval path — a fully separate, precision-based
    lookup over the term->article inverted index, completely bypassing RRF/vector
    retrieval (023-article-search follow-up: RRF's candidate_k bound and embedding-space
    ranking give no guarantee a literal match is even in the candidate set, let alone
    ranked highly — see `_exact_match_article_ids`'s docstring). Ordered newest-first
    (`_fetch_articles_by_ids`) by default, since there's no RRF score here to order by —
    `sort`/`order` (see `_reorder_by_field`) can override that when the visitor picked an
    explicit sort. `filtered_ids` (see `_filtered_article_ids`) is AND-intersected with the
    inverted-index candidates before fetching full rows, same "narrow before pagination"
    reasoning as the RRF path."""
    exact_match_ids = _exact_match_article_ids(db, query, topic_id, lang)
    if not exact_match_ids:
        return PaginatedArticles(items=[], total=0, page=page, size=size)
    if filtered_ids is not None:
        exact_match_ids = exact_match_ids & filtered_ids
    if not exact_match_ids:
        return PaginatedArticles(items=[], total=0, page=page, size=size)

    rows = _fetch_articles_by_ids(db, exact_match_ids, topic_id)
    rows = _reorder_by_field(rows, sort, order, key_fn=lambda row: row[sort] if sort else None)
    total = len(rows)

    offset = (page - 1) * size
    page_rows = rows[offset:offset + size]

    trans_map: dict = {}
    if lang != "en" and page_rows:
        trans_map = _fetch_translations(db, [str(row["id"]) for row in page_rows], lang)

    items = []
    for row in page_rows:
        translation = trans_map.get(str(row["id"]))
        items.append(ArticleOut(
            id=row["id"], url=row["url"], source=row["source"], title=row["title"], content=row["content"],
            published_at=row["published_at"], scraped_at=row["scraped_at"],
            translated_title=translation.get("title") if translation else None,
            translated_content=translation.get("content") if translation else None,
            exact_match=True,
        ))
    event_logger.info(
        "search_query_executed",
        topic_id=str(topic_id) if topic_id else None,
        exact_match_only=True,
        candidate_total=total,
    )
    return PaginatedArticles(items=items, total=total, page=page, size=size)


async def search_articles_hybrid(
    db: Session, query: str, topic_id: Optional[UUID], page: int, size: int,
    exact_match_only: bool = False, lang: str = "en",
    aggregators: Optional[list] = None, original_sources: Optional[list] = None,
    tags: Optional[list] = None, tag_groups: Optional[list] = None,
    published_after: Optional[date] = None, published_before: Optional[date] = None,
    scraped_after: Optional[date] = None, scraped_before: Optional[date] = None,
    sort: Optional[str] = None, order: str = "desc",
) -> PaginatedArticles:
    """`aggregators`/`original_sources`/`tags`/`tag_groups`/`published_*`/`scraped_*` mirror
    `GET /articles`' own filter params exactly (see `_filtered_article_ids`) — narrowing
    the candidate pool *before* RRF/exact-match ranking and pagination, not filtering the
    page of already-ranked results after the fact, for the same "total/pagination must
    agree with what's shown" reasoning `exact_match_only` already established.

    `sort`/`order` are `None`/`"desc"` by default, meaning "no override" — the frontend
    only ever sends an explicit `sort` once the visitor has actually picked one (see
    frontend/lib/api/search.ts and articles-page-content.tsx's `hasExplicitSort`), so by
    default this still preserves pure RRF-relevance order for the hybrid path and newest-
    first for the exact-match path (see `_reorder_by_field`) — an unset/unrecognized `sort`
    is a deliberate zero-behavior-change no-op, not "sort by nothing."

    `exact_match_only=True` delegates entirely to `_search_exact_match_only` — a
    separate, precision-based retrieval path over the term->article inverted index, not a
    post-hoc filter on top of RRF (023-article-search follow-up: RRF's candidate_k bound
    and embedding-space ranking give no guarantee a literal match even appears in RRF's
    candidates, let alone ranks highly there — see `_exact_match_article_ids`'s docstring
    for the full reasoning "why doesn't exact match just rank first").

    Otherwise (default), hybrid sparse+dense search over vectors.article_chunks, merged
    via RRF — results are ordered purely by RRF score, no re-ranking or candidate
    injection on top of it (an earlier revision added both — literal-match ILIKE
    candidate injection and a boost_exact_match reorder step — deliberately reverted in
    favor of this simpler design). Each item's `exact_match` flag is still annotated, via
    the exact same inverted-index lookup `exact_match_only` uses as its sole candidate
    source — not a plain substring check — so the flag can never disagree with what
    autocomplete's occurrence_count promises (the original bug this whole redesign fixed).

    Degrades to whichever of sparse/dense is actually configured (RAG_DENSE_PROVIDER/
    RAG_SPARSE_PROVIDER empty means that provider is skipped — see `embed_query`) —
    mirrors chatbot_plugin_sdk's own RetrieveProcessor, which does the same "hybrid if
    both, else whichever one" fallback.

    `lang` (default "en", matching every other lang-aware endpoint's convention) controls
    both which translated title/content get surfaced on each result (mirrors
    build_articles_list_payload's ArticleTranslation lookup for GET /articles) and — since
    a non-English query can only ever literally match the corresponding translation, never
    the English original — which language's terms `exact_match`/`exact_match_only` are
    checked against."""
    filtered_ids = _filtered_article_ids(
        db, topic_id, aggregators, original_sources, tags, tag_groups,
        published_after, published_before, scraped_after, scraped_before,
    )

    if exact_match_only:
        return _search_exact_match_only(
            db, query, topic_id, page, size, lang,
            filtered_ids=filtered_ids, sort=sort, order=order,
        )

    exact_match_ids = _exact_match_article_ids(db, query, topic_id, lang) or set()

    candidate_k = size * _CANDIDATE_MULTIPLIER

    sparse_weights, dense_values = await embed_query(query)
    if sparse_weights is None and dense_values is None:
        raise ExternalDependencyError("Neither a dense nor a sparse embedding provider is configured")

    sparse_rows = (
        _run_vector_query(
            db, "sparse_vector", "sparsevec", _sparse_vec_literal(sparse_weights), topic_id, candidate_k,
            filtered_ids=filtered_ids,
        )
        if sparse_weights is not None else []
    )
    dense_rows = (
        _run_vector_query(
            db, "dense_vector", "vector", _dense_vec_literal(dense_values), topic_id, candidate_k,
            filtered_ids=filtered_ids,
        )
        if dense_values is not None else []
    )

    merged = _rrf_merge(dense_rows, sparse_rows)
    merged = _reorder_by_field(merged, sort, order, key_fn=lambda pair: pair[0][sort] if sort else None)

    offset = (page - 1) * size
    page_rows = merged[offset:offset + size]

    # Fetched only for the final page, not the full pre-pagination candidate set — unlike
    # the old substring `_is_exact_match` check, the inverted-index-based `exact_match`
    # annotation above no longer depends on translation text, so translations are now
    # purely a display concern (translated_title/translated_content).
    trans_map: dict = {}
    if lang != "en" and page_rows:
        trans_map = _fetch_translations(db, [str(row["id"]) for row, _score in page_rows], lang)

    exact_match_str_ids = {str(article_id) for article_id in exact_match_ids}
    items = []
    for row, _score in page_rows:
        translation = trans_map.get(str(row["id"]))
        items.append(ArticleOut(
            id=row["id"], url=row["url"], source=row["source"], title=row["title"],
            content=row["content"], published_at=row["published_at"], scraped_at=row["scraped_at"],
            translated_title=translation.get("title") if translation else None,
            translated_content=translation.get("content") if translation else None,
            exact_match=str(row["id"]) in exact_match_str_ids,
        ))
    event_logger.info(
        "search_query_executed",
        topic_id=str(topic_id) if topic_id else None,
        sparse_candidates=len(sparse_rows),
        dense_candidates=len(dense_rows),
        merged_total=len(merged),
    )
    return PaginatedArticles(items=items, total=len(merged), page=page, size=size)


_CJK_CHAR = re.compile(r"[一-鿿]")  # same range as src/modules/search/domain/services/tokenizer.py's _CJK_CHAR


def _prefix_suggestable_for_lang(prefix: str, lang: str) -> bool:
    """False for a CJK prefix when `lang` isn't a Chinese locale — suggesting it would be
    a dead end, since _exact_match_article_ids' inverted-index lookup (and therefore the
    only way a CJK query can ever literally match anything) is itself gated on `lang`. A
    non-CJK prefix is always suggestable regardless of `lang`, since it can still match
    the "en"-language index unconditionally — mirrors _exact_match_article_ids' own
    asymmetry (original/"en" terms always searchable, a translation's terms only when
    `lang` selects that language)."""
    if not _CJK_CHAR.search(prefix):
        return True
    return lang.lower().startswith("zh")


def _find_matching_terms(db: Session, topic_id: Optional[UUID], prefix: str, lang: str, limit: int) -> list:
    """Postgres fallback for autocomplete when Redis is unavailable or the key was never
    built — direct ORM query against models.SearchTerm (023-article-search follow-up:
    replaced the raw-SQL SqlAlchemySearchTermRepository so this lookup is consistent with
    the rest of backend/'s ORM+injected-Session convention, and so it can filter by
    `language` now that intelligence.search_terms splits terms by language).

    Unlike the Redis trie (which stays language-blind — see RebuildSearchIndexUseCase),
    this fallback filters on `language == lang`: it's rare (Redis miss/outage only), so
    there's no existing UX consistency guarantee to preserve, and filtering here is what
    keeps a zh-TW suggestion from being offered in an English UI (dead end once submitted,
    same reasoning as `_prefix_suggestable_for_lang`)."""
    from models.search_term import SearchTerm as SearchTermModel
    from shared.search_index.search_term import SearchTerm as SearchTermDTO

    if topic_id is None:
        return []
    rows = (
        db.query(SearchTermModel.term, SearchTermModel.occurrence_count)
        .filter(
            SearchTermModel.topic_id == topic_id,
            SearchTermModel.language == lang,
            SearchTermModel.term.ilike(f"%{prefix}%"),
        )
        .order_by(SearchTermModel.occurrence_count.desc())
        .limit(limit)
        .all()
    )
    return [SearchTermDTO(term=row.term, occurrence_count=row.occurrence_count) for row in rows]


def suggest_terms(db: Session, topic_id: Optional[UUID], prefix: str, limit: int = 10, lang: str = "en") -> AutocompleteResponse:
    """Autocomplete lookup — Redis-first (fast path), falls back to the Postgres
    intelligence.search_terms table on a Redis miss/outage. Never raises for a
    lookup failure; degrades to an empty suggestion list (spec Edge Cases).

    `lang` (default "en") gates CJK suggestions to Chinese locales — see
    `_prefix_suggestable_for_lang`. Binds autocomplete to the same UI-language contract
    `search_articles_hybrid`'s `lang` already has, so a suggestion is never offered for a
    query that couldn't actually find anything once submitted (023-article-search
    follow-up)."""
    if not _prefix_suggestable_for_lang(prefix, lang):
        return AutocompleteResponse(suggestions=[])

    from shared.search_index import RedisSearchIndexGateway
    from backend.config import SEARCH_INDEX_REDIS_URL

    lookup = prefix[:SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN]
    gateway = RedisSearchIndexGateway(redis_url=SEARCH_INDEX_REDIS_URL)
    terms = gateway.suggest(topic_id=topic_id, prefix=lookup, limit=limit)
    source = "redis"

    if terms is None:  # Redis unavailable or the key was never built — fall back to Postgres
        source = "postgres_fallback"
        terms = _find_matching_terms(db, topic_id=topic_id, prefix=prefix, lang=lang, limit=limit)
        try:
            gateway.repopulate(topic_id=topic_id, prefix=lookup, terms=terms)
        except Exception:
            logger.warning("search_suggest_redis_repopulate_failed", exc_info=True)
    elif len(prefix) > SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN:
        terms = [t for t in terms if prefix in t.term]

    event_logger.info(
        "search_autocomplete_executed",
        topic_id=str(topic_id) if topic_id else None,
        source=source,
        suggestion_count=len(terms),
    )
    return AutocompleteResponse(suggestions=[SearchSuggestion(term=t.term, occurrence_count=t.occurrence_count) for t in terms])
