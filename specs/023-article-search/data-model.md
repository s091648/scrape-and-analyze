# Phase 1 Data Model: Article Search & Autocomplete

The hybrid RRF search query reads an existing, already-populated table via raw SQL (see research.md), and autocomplete's suggestion trie lives entirely in Redis — neither needed a migration or ORM model. `exact_match`/`exact_match_only`, however, are now backed by a real term->article inverted index (`intelligence.search_terms` + `intelligence.search_term_articles` — migration `26_add_search_terms_and_pg_trgm.py`, ORM models `models/search_term.py`/`models/search_term_article.py`), added in a 023-article-search follow-up once an earlier substring-based `exact_match` check was found to disagree with autocomplete's own `occurrence_count` for Chinese queries (jieba tokenizes "遊戲化" as one term distinct from "遊戲" — a substring check couldn't see that distinction, but the same tokenizer-driven inverted index both features now share can). This file documents the concrete shape of all of it.

## Search query (Postgres, raw SQL — no ORM)

**Source tables** (all pre-existing, migration 21 + 25, schema per `site/guide/architecture/db-schema.md`):

| Table | Relevant columns | Role |
|---|---|---|
| `vectors.article_chunks` | `id`, `article_id → vectors.articles.id`, `chunk_index`, `content`, `sparse_vector SPARSEVEC(30522)` | One row per chunk; `sparse_vector` is what gets compared against the query embedding |
| `vectors.articles` | `id`, `url`, `title`, `source`, `public_article_id → core.articles.id` (nullable), `topic_id`, `metadata` | Denormalized parent; bridges to the real article via `public_article_id` |
| `core.articles` | `id`, `url`, `source`, `title`, `content`, `published_at`, `scraped_at`, `topic_id`, `has_vectors`, ... (full `ArticleOut` field set) | The real entity — response payload is built from here, not from `vectors.articles`'s denormalized copy |

**Query shape — hybrid sparse + dense, merged via RRF (research.md "Decision: Hybrid sparse + dense search via RRF")**:

Two parallel queries, same shape, different vector column/operator:

```sql
-- Sparse (keyword-shaped)
SELECT a.id, a.url, a.source, a.title, a.content, a.published_at, a.scraped_at,
       MIN(ac.sparse_vector <=> CAST(:query_sparse_vec AS sparsevec)) AS best_distance
FROM vectors.article_chunks ac
JOIN vectors.articles va ON ac.article_id = va.id
JOIN core.articles a ON a.id = va.public_article_id
WHERE ac.sparse_vector IS NOT NULL
  AND a.topic_id = :topic_id           -- FR-009
  AND a.merged_into_id IS NULL         -- exclude tombstoned duplicates (migration 25)
GROUP BY a.id
ORDER BY best_distance
LIMIT :candidate_k                     -- top_k * 3, headroom for RRF re-ranking

-- Dense (semantic) — identical shape, swap the vector column/operator
SELECT a.id, a.url, a.source, a.title, a.content, a.published_at, a.scraped_at,
       MIN(ac.dense_vector <=> CAST(:query_dense_vec AS vector)) AS best_distance
FROM vectors.article_chunks ac
JOIN vectors.articles va ON ac.article_id = va.id
JOIN core.articles a ON a.id = va.public_article_id
WHERE ac.dense_vector IS NOT NULL
  AND a.topic_id = :topic_id
  AND a.merged_into_id IS NULL
GROUP BY a.id
ORDER BY best_distance
LIMIT :candidate_k
```

Both result sets are merged in Python via RRF (`score = Σ 1/(60 + rank + 1)` across the two ranked lists), then the top `:size` (after `:offset`) survive into the response.

- **`<=>` (cosine distance), never `<#>`** — matches `idx_article_chunks_sparse_vector`'s `sparsevec_cosine_ops` opclass *and* `idx_article_chunks_dense_vector`'s `vector_cosine_ops` (see research.md's operator-class pitfall — both of scrape-analyzer's own indexes use cosine, unlike `chatbot-plugin-sdk`'s inner-product sparse index).
- `GROUP BY a.id` / `MIN(distance)` — an article can have multiple chunks; rank by its single best-matching chunk per query type, not one row per chunk.
- `a.merged_into_id IS NULL` — excludes tombstoned duplicate articles (`025_add_article_merge_tombstone`), consistent with how the existing `GET /articles` listing already has to treat merged rows (verify exact existing predicate in `article_service.py` during implementation — this row should match it, not diverge from it).
- `:query_sparse_vec`/`:query_dense_vec` come from two fastembed embedding calls (sparse + dense — research.md), the query text itself is never embedded/stored, only used transiently per-request.

**No-results case (FR-003)**: an empty result set from this query is not an error — `backend/services/search_service.py` returns `PaginatedArticles(items=[], total=0)`, same emptiness shape the existing `GET /articles` endpoint already uses for "no matches," so the frontend's existing empty-state handling can potentially be reused as-is.

**How RRF results are ordered, and why `exact_match` doesn't imply "ranked first"**: each candidate's final score is `Σ 1/(60 + rank + 1)` across whichever of the sparse/dense ranked lists it appears in — purely a function of embedding-space cosine-distance rank, with no awareness of literal keyword containment. A perfect substring match can rank low (or fall outside `:candidate_k` entirely) if its containing chunk's overall vector happens to sit further from the query embedding than another, purely-semantic neighbor's — this is expected, not a bug, and is exactly why `exact_match_only` (below) is a wholly separate retrieval path rather than a re-ranking step on top of RRF.

## Exact-match retrieval (`exact_match_only=true`) — bypasses RRF entirely

Per-item `exact_match` (always computed) and the `exact_match_only=true` retrieval path (023-article-search follow-up) are both driven by the term->article inverted index below, via an **AND-intersection** across the query's tokens — user-confirmed design: a multi-token query only matches an article containing *every* token; articles that are merely related to some of the tokens are hybrid RRF's job, not this path's.

```sql
-- Conceptual shape of _exact_match_article_ids (backend/services/search_service.py) —
-- actually built with the ORM (SQLAlchemy Core-compiled, not raw text()), since neither
-- table here needs to join vectors.* (the one thing that forces raw SQL above).
SELECT sta.article_id
FROM intelligence.search_term_articles sta
JOIN intelligence.search_terms st ON st.id = sta.search_term_id
WHERE st.language = :lang
  AND st.term IN (:token1, :token2, ...)     -- tokenize(query), same tokenizer as index-build time
  AND st.topic_id = :topic_id                -- omitted entirely when topic_id is None (global search)
GROUP BY sta.article_id
HAVING COUNT(DISTINCT st.term) = :token_count -- AND semantics: every token must be present
```

- `exact_match_only=true`: this ID set (with `merged_into_id IS NULL`/`topic_id` re-checked at request time via a `core.articles` fetch, raw SQL again — see below) is the **entire** candidate pool, paginated newest-first (`published_at DESC`) — no RRF, no vector query, no `embed_query()` call at all.
- `exact_match_only=false` (default): the same ID set is computed once and used only to annotate each RRF result's `exact_match` flag (`row.id in exact_match_ids`) — RRF's own candidate retrieval and ordering are completely untouched.
- `query` tokenizes to nothing (e.g. entirely stopwords) → the lookup returns `None`, treated as "no exact-match signal" (empty candidate pool / every `exact_match` flag `False`), not an error.
- The final article-detail fetch for `exact_match_only`'s candidate pool (`_fetch_articles_by_ids`) is raw SQL against `core.articles`, not the ORM — same reasoning as the hybrid query above (and, in the integration test harness specifically, required to see the same schema `core.articles`/`vectors.*` fixtures are seeded into; see `backend/tests/integration/test_search.py`'s module docstring).

## Autocomplete index (Redis — the "prefix tree", dedicated DB) + Postgres fallback

Everything below lives in the Redis DB backing `SEARCH_INDEX_REDIS_URL` (research.md — a new dedicated logical DB, e.g. db 2, distinct from `REDIS_URL`/`CACHE_REDIS_URL`), **plus** a compact Postgres table that backs a cache-aside fallback (research.md "Decision: Persist the compact term list in Postgres"). Nothing in Redis is a TTL'd cache-aside entry — the whole DB is the primary source for suggestions between rebuilds, wholesale rewritten each cycle (FR-008); Postgres is what a Redis miss/outage falls back to.

### Suffix-expanded prefix entry (Redis `ZSET`)

- **Key**: `search:idx:{topic_id}:{s}`
  - `topic_id` — FR-009 requires suggestions scoped to the visitor's current topic, so the index is partitioned per topic (not one global index filtered at read time) — keeps the read path a single `ZREVRANGE`, no post-filtering.
  - `s` — normalized (lowercased, trimmed) (suffix-)prefix, 1 to `MAX_PREFIX_LEN` (**`C=8`**) characters. Per research.md's suffix-expansion decision, every complete term produces one entry for **every prefix of every suffix of itself**, capped at `C` characters — not just its own prefixes — so a typed substring matches a term regardless of where in the term it occurs.
- **Members**: complete terms (the full word, not the prefix/suffix fragment) — e.g. querying `search:idx:{topic}:arn` can return `learning` (via its suffix `arning`), not `arn` itself unless `arn` is also a term that actually occurs.
- **Score**: the term's `occurrence_count` for that topic (document frequency, `MIN_DOC_FREQ`-filtered — research.md) — `ZREVRANGE ... WITHSCORES` gives ranked results directly.
- **Read**: `ZREVRANGE search:idx:{topic_id}:{s[:C]} 0 9` → top-10 candidates; if the visitor's typed text is longer than `C`, the lookup uses only its first `C` characters and `search_service.py` **post-filters** the ≤10 candidates to those that still contain the full typed text (research.md — keeps contains-matching correct past the cap).
- **Write**: only ever produced by a full-DB rebuild (`SearchIndexRebuildHandler` → `RedisSearchIndexGateway.rebuild(...)`), via a Redis **pipeline** (batched — tens of thousands of `ZADD` calls per rebuild, one round-trip per call would dominate wall-clock time), never incrementally mutated by a read request.

### Rebuild marker key

- **Key**: `search:idx:rebuilt_at`
- **Value**: ISO-8601 timestamp of the last successful rebuild completion.
- **Purpose**: lets `GET /search/autocomplete` degrade gracefully (spec Edge Cases: "underlying suggestion data is being rebuilt and briefly unavailable") — if this key is absent (first-ever rebuild not yet finished) or the whole DB is empty, the endpoint falls back to the Postgres table below rather than erroring. Not a correctness-critical value (no reads gate on its age), purely an observability/debugging aid — same posture as `CacheGateway`'s "never raises" philosophy.

### `intelligence.search_terms` (Postgres table + ORM model `models/search_term.py`)

The compact, pre-expansion source Redis is derived from — **not** a copy of the expanded structure above. Also now the language-scoped natural key `intelligence.search_term_articles` FKs into.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | Surrogate PK — `search_term_articles.search_term_id`'s FK target |
| `topic_id` | `UUID` | FK-equivalent to `core.topics.id` (no formal FK — matches how `vectors.articles.topic_id` is also unenforced) |
| `term` | `TEXT` | The complete tokenized term |
| `language` | `VARCHAR(10)` | Added in a 023-article-search follow-up, same one-row-per-language pattern as `ArticleTranslation`/`AnalysesTranslation`/etc — `"en"` for the article's original text, or the corresponding `ArticleTranslation.language` for a translated term. Without this, a non-English query's inverted-index lookup couldn't tell a zh-TW term apart from an English one that happens to share the same string |
| `occurrence_count` | `INTEGER` | Distinct-article count for `(topic_id, term, language)` — **not** `MIN_DOC_FREQ`-filtered (unlike the Redis trie below): this table is exact-match retrieval's completeness guarantee, so a term used in only one article must still get a row, even though it'd never be worth surfacing as an autocomplete suggestion |

- **Constraints/Indexes**: `UNIQUE (topic_id, term, language)` — both the natural key and the target the rebuild's replace-all write re-derives; `idx_search_terms_topic_language (topic_id, language)` for the equality prefilter; a `pg_trgm` GIN index on `term` so the Postgres-fallback autocomplete's `ILIKE '%...%'` contains-query doesn't sequential-scan.
- **Written by**: `RebuildSearchIndexUseCase` via `src/infrastructure/persistence/intelligence/search_term_repo_impl.py::SqlAlchemySearchTermRepository` (ORM, not raw SQL — see below), one atomic transaction per rebuild, **before** the Redis write (research.md's write-order decision).
- **Read by**: `backend/services/search_service.py`'s `_find_matching_terms` (autocomplete's Postgres fallback, ORM query filtered by `topic_id`/`language`/`term ILIKE`) and `_exact_match_article_ids` (the inverted-index AND-intersection lookup, joined against `search_term_articles` — see "Exact-match retrieval" above).

### `intelligence.search_term_articles` (Postgres table + ORM model `models/search_term_article.py`)

The term->article inverted index itself — one row per `(term, article)` pair the term literally occurs in. New in a 023-article-search follow-up.

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | Surrogate PK |
| `search_term_id` | `UUID` | FK → `intelligence.search_terms.id`, `ON DELETE CASCADE` |
| `article_id` | `UUID` | FK → `core.articles.id`, `ON DELETE CASCADE` |

- **Constraints/Indexes**: `UNIQUE (search_term_id, article_id)` (also the composite index the AND-intersection join scans, leading on `search_term_id`); `idx_search_term_articles_article_id (article_id)`.
- **Populated for every distinct term the tokenizer finds** — deliberately not `MIN_DOC_FREQ`-filtered, same reasoning as `search_terms.occurrence_count` above.
- **ORM, not raw SQL** — unlike `core.articles`/`vectors.*` (raw SQL throughout `search_service.py`, forced by `vectors.article_chunks`' fixed, non-per-test-isolated schema needing to join a matching `core.articles` row), neither this table nor `search_terms` needs that join, so `search_service.py` queries them the same way most other backend services query the ORM: directly via the injected `Session`, no repository wrapper (023-article-search follow-up: an earlier revision used a raw-SQL `shared/search_index/search_term_repo_impl.py` repository class here, replaced once this inconsistency with the rest of the codebase's style was raised).

### Rebuild procedure (conceptual — full detail in tasks.md)

1. `RebuildSearchIndexUseCase` queries `core.articles` LEFT JOIN `core.articles_translation` (`title`/`content`/translation `language`+`title`+`content`, non-tombstoned — `merged_into_id IS NULL`), grouped by `topic_id`.
2. Tokenizes each article's text (`shared/search_index/tokenizer.py` — `jieba` + `stopwordsiso` for zh-TW, simple split + `stopwordsiso` for English; moved here from `src/modules/search/domain/services/` in a follow-up so `backend/services/search_service.py` can tokenize a query string with the identical algorithm at retrieval time) into a set of *distinct* terms per article, length ≥ 2 — tracked **twice**, in parallel: a language-blind union (original + every translation's terms merged together) for the Redis trie, and a language-split breakdown (original tagged `"en"`, each translation tagged its own `language`) for `intelligence.search_terms`/`search_term_articles`.
3. Aggregates the language-blind terms into per-topic term → document-frequency counts; drops terms below `MIN_DOC_FREQ` (2) — this filtered map is the Redis trie's input only.
4. Aggregates the language-split terms into `{(topic_id, term, language): {article_ids}}` — **unfiltered** — and writes it into `intelligence.search_terms`/`search_term_articles` (Postgres, atomic transaction, `occurrence_count` derived as `len(article_ids)`).
5. Expands each *filtered, language-blind* `(topic_id, term)` into its capped suffix-prefix set (research.md) and writes into a **new, empty** logical Redis DB state via pipelined `ZADD`s.
6. Atomically swaps the freshly-built Redis state in for reads (`SWAPDB` against a staging DB index — avoids any window where autocomplete serves a half-rebuilt index; O(1)).
7. Sets `search:idx:rebuilt_at`.

## Response schemas (`backend/schemas/search.py`, Pydantic)

| Schema | Fields | Used by |
|---|---|---|
| `PaginatedArticles` (existing, reused as-is) | `items: List[ArticleOut]`, `total: int` | `GET /search` |
| `SearchSuggestion` (new) | `term: str`, `occurrence_count: int` | `GET /search/autocomplete` |
| `AutocompleteResponse` (new) | `suggestions: List[SearchSuggestion]` | `GET /search/autocomplete` |

Reusing `ArticleOut`/`PaginatedArticles` for search results (rather than inventing a new `SearchResultOut`) is deliberate: it's the same shape the articles list already renders, which is what keeps "reuse the existing article list UI for search results" (spec.md Assumptions — deferred presentation-layer decision) actually viable at the frontend without a schema translation layer in between.
