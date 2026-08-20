# Contract: Search & Autocomplete Endpoints

Two new endpoints on a new `backend/routers/search.py`. Both require `require_any_token` (FR-012 — guest or logged-in, matching every other articles-adjacent endpoint) and are topic-scoped (FR-009).

## `GET /search`

Keyword search over articles (FR-001–FR-003, FR-010).

**Query parameters**:

| Param | Type | Required | Notes |
|---|---|---|---|
| `q` | string | yes | The search query. Empty/whitespace-only after trim → `400` (Edge Cases: no search should run) |
| `topic_id` | UUID | no | Same semantics as `GET /articles`'s `topic_id` — omitted means the visitor's resolved default topic |
| `page` | int | no, default 1 | Matches `GET /articles`'s pagination convention |
| `size` | int | no, default 20, max 100 | Matches `GET /articles`'s pagination convention |
| `lang` | string | no, default "en" | Matches existing convention. Controls which translated `translated_title`/`translated_content` are surfaced (mirrors `GET /articles`) — never changes which articles are *retrieved* (RRF runs on `q`'s embedding regardless of `lang`). Does affect `exact_match`, though: a non-English `q` can only ever literally match `core.articles_translation`'s text for that `lang`, never `core.articles`' English original, so it's checked against the `lang` translation when one exists |
| `exact_match_only` | bool | no, default `false` | Switches to a fully separate retrieval path over the term->article inverted index (AND-intersection across the query's tokens), bypassing RRF/vector retrieval entirely — see "Behavioral notes" below. Backs the frontend's "exact matches only" checkbox (defaults to checked); a help tooltip next to the checkbox explains that unchecking it switches to keyword + semantic hybrid retrieval |

**Response** `200 OK`, body: `PaginatedArticles` (existing schema, reused — data-model.md), each item additionally carrying `exact_match: bool` (whether `q` occurs verbatim, case-insensitive, in that article's title/content):
```json
{ "items": [ { "id": "...", "url": "...", "title": "...", "content": "...", "exact_match": true, "...": "..." } ], "total": 12 }
```
An empty `items`/`total: 0` is the normal "no results" response (FR-003) — not an error.

**Response** `400 Bad Request`: empty/whitespace-only `q`, via the standard `ErrorResponse` shape (`017-exception-handling-guideline`'s `ValidationError` category) — routers never construct `HTTPException` directly per that guideline.

**Response** `401 Unauthorized`: no valid token (guest or otherwise) presented.

**Behavioral notes**:
- When `exact_match_only=false` (default): embeds `q` into **both** a sparse and a dense vector via `chatbot_plugin_sdk` provider classes (`GeminiDenseProvider` / `EndpointProvider`, selected by `build_dense_provider`/`build_sparse_provider` from `backend/config.py`'s `RAG_DENSE_*`/`RAG_SPARSE_*` — the *same* config `src/`'s RAG ingestion pipeline uses to embed articles into `vectors.article_chunks`, so query and article vectors are guaranteed to land in the same space), then runs both the sparse and dense candidate queries, merges via Reciprocal Rank Fusion (`k=60`), returns the fused top-N **in pure RRF-score order** — no re-ranking or candidate injection on top of it. This is the one part of the request that isn't a pure DB round-trip; no explicit SLA is set for `GET /search` itself (only autocomplete has a hard latency requirement, FR-011). RRF's score is purely a function of embedding-space cosine-distance rank — it has no awareness of literal keyword containment, so a genuine exact match can rank low or fall outside `candidate_k` entirely while a purely-semantic neighbor with no literal match ranks first; this is expected, not a bug (data-model.md's "How RRF results are ordered" explains why), and is exactly why `exact_match_only` is a separate path rather than a re-rank of these results.
- When `exact_match_only=true`: **bypasses RRF/vector retrieval entirely.** Tokenizes `q` (same tokenizer `RebuildSearchIndexUseCase` used to build the index — `shared/search_index/tokenizer.py`) and looks up the AND-intersection of every token's article set in the term->article inverted index (`intelligence.search_terms`/`search_term_articles` — data-model.md's "Exact-match retrieval" section) — a multi-token query only matches an article containing *every* token (user-confirmed design: articles merely related to some tokens are hybrid RRF's job, not this path's). This candidate set is the *entire* result pool, paginated newest-first (`published_at DESC`) — no `candidate_k` bound, no embedding call, no dependency on the article even having any `vectors.article_chunks` rows at all.
- `exact_match` (per-item, always computed on the RRF path; trivially `true` on the `exact_match_only` path) comes from the same inverted-index lookup, not a substring check — replacing an earlier plain-substring `_is_exact_match`, which could disagree with autocomplete's `occurrence_count` whenever jieba folded a query into a larger compound term (e.g. a "遊戲" query wouldn't flag an article containing only "遊戲化"); using the identical tokenizer+index both features now share closes that gap by construction. `lang` (default `"en"`) scopes which language's terms are searched: `"en"` only ever matches the original scraped-language text, any other value only ever matches that language's `core.articles_translation` row — mirrors every other lang-aware endpoint's convention.
- Stale/superseded requests (Edge Cases: "user submits a search while a previous search... is still in flight") are a frontend-side concern (AbortController / request-generation-tracking on the client), not a backend contract concern — the backend has no notion of "in-flight" requests to cancel.

## Decision: query embedding via `chatbot_plugin_sdk`, not a direct `fastembed` call (023-article-search follow-up)

**Problem observed**: autocomplete's `occurrence_count` (word-segmentation-based document frequency, `intelligence.search_terms`) didn't match how many articles `GET /search` could actually find for the same term — most visibly for Traditional Chinese queries. Root cause: the endpoint's original `embed_query()` POSTed directly to the shared `fastembed` service for *both* sparse and dense in one call, but that deployment's `EMBED_DENSE_MODEL` was never configured, so dense silently came back `null` — `GET /search` was running **sparse-only**, on `Splade_PP_en_v1` (English-only), which has essentially no signal for a CJK query's candidate ranking.

**Decision**: `embed_query()` now builds dense/sparse providers via `chatbot_plugin_sdk`'s `build_dense_provider()`/`build_sparse_provider()` factories, reading the same `RAG_DENSE_*`/`RAG_SPARSE_*` config `src/bootstrap.py::build_collection_pipeline()` already uses for RAG ingestion (`backend/config.py` mirrors `src/config/settings.py`'s block exactly). `backend`'s dependency group in `pyproject.toml` gained `chatbot-plugin-sdk` for this (previously scraper-only); `backend/Dockerfile`/`Dockerfile.dev` gained `git` (uv needs it to fetch the SDK's git-tag dependency). Only the provider *classes* are reused, not the SDK's `RetrieveProcessor`/`AsyncPgBackend` — those are chunk-level and would need translating back into this endpoint's article-level, `exact_match`-aware, translation-aware shape anyway, and would introduce a second DB connection pool into `backend` for a table it already queries directly via the existing SQLAlchemy `Session`.

**Consequence**: query embeddings now land in the exact same vector space as the stored article vectors (both ultimately Gemini, when `RAG_DENSE_PROVIDER=gemini`), which is what actually fixed dense retrieval.

## Decision history: from substring `exact_match` to a term->article inverted index (023-article-search follow-up, supersedes two earlier revisions of this contract)

Three designs were tried, in order:

1. **Literal-match candidate injection + re-ranking.** Built to compensate for the dense-embedding bug above: `_fetch_literal_match_candidates()` (an `ILIKE '%q%'` query against `core.articles`/`core.articles_translation`, backed by four trgm GIN indexes) injected any literally-matching article RRF's bounded candidate retrieval missed, and `boost_exact_match` stable-sorted `exact_match: true` results ahead of the rest. **Reverted**: added architectural complexity (a re-ranking step, four extra indexes) that the user judged not worth it relative to the completeness gap it closed.
2. **Plain substring `exact_match`, pure RRF order.** `exact_match` became a post-hoc `q in title/content` check (also checking the `lang` translation), computed only over whatever RRF retrieved; `exact_match_only` filtered that same list pre-pagination. Simpler, but the substring check could disagree with autocomplete's `occurrence_count` (a word-segmentation-based count) whenever jieba's tokenizer folded the query into a larger compound term — e.g. a "遊戲" query wouldn't flag an article containing only "遊戲化" as an exact match, since `intelligence.search_terms` never counted "遊戲化" toward "遊戲"'s occurrence either, but a plain substring check *would* have matched it (or vice versa depending on phrasing). **Superseded**: this inconsistency between what autocomplete promises and what search's `exact_match` badge shows was the whole reason this feature exists.
3. **Term->article inverted index (current).** `intelligence.search_terms` gained a `language` column and a new sibling table, `intelligence.search_term_articles` (one row per term/article pair the term occurs in, populated by the same tokenizer autocomplete's index uses — data-model.md). `exact_match`/`exact_match_only` now query this index directly (AND-intersection across the query's tokens) instead of a substring check, and `exact_match_only=true` became a **fully separate retrieval path** bypassing RRF entirely rather than a post-hoc filter on it — RRF's candidate_k bound and embedding-space ranking never guaranteed a literal match would even be a *candidate*, let alone rank highly (data-model.md's "How RRF results are ordered"), so filtering *its* output could never have been a completeness guarantee anyway. This is the first design where `exact_match`'s value is now guaranteed consistent with autocomplete's `occurrence_count` by construction, since both are now views over the same underlying `(term, article, language)` data.

The four trgm GIN indexes from design 1 were dropped as part of design 2's revert; `intelligence.search_terms`'s own trgm GIN index (`idx_search_terms_term_trgm`, for the Postgres-fallback autocomplete lookup) predates all of this and is unrelated.

## `GET /search/autocomplete`

Real-content suggestions as the user types (FR-004, FR-006, FR-011).

**Query parameters**:

| Param | Type | Required | Notes |
|---|---|---|---|
| `prefix` | string | yes | The characters typed so far. Empty/whitespace-only → `400`, same as `q` above. If longer than `SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN` (`.env.example`, `C=8`), the server truncates to the first `C` characters for its Redis lookup and post-filters candidates to those that still contain the full `prefix` (research.md) — callers do not need to pre-truncate themselves, though the frontend does so anyway (see below) to avoid the round-trip entirely |
| `topic_id` | UUID | no | Same resolution as `GET /search` |
| `lang` | string | no, default "en" | A CJK `prefix` returns `{"suggestions": []}` immediately (no Redis/Postgres lookup at all) unless `lang` is a Chinese locale — a CJK query can only ever literally match via `GET /search`'s translation lookup (itself gated on `lang`), so suggesting one in a non-Chinese UI would offer a suggestion that leads to a dead-end search once submitted. A non-CJK `prefix` is never gated, regardless of `lang` — it can still match the English original unconditionally |

**Response** `200 OK`:
```json
{ "suggestions": [ { "term": "learning", "occurrence_count": 42 }, { "term": "learned", "occurrence_count": 7 } ] }
```
- Ordered by `occurrence_count` descending (already ranked server-side — the frontend must not re-sort).
- An empty `suggestions` array is the normal "no matches" response (spec Acceptance Scenario 4) — including when the underlying index hasn't finished its first rebuild yet, or a Redis miss/outage fell through to the `intelligence.search_terms` Postgres fallback and *that* also had nothing (data-model.md). This endpoint follows `CacheGateway`'s "never raises" posture end-to-end (Redis error → Postgres fallback → empty list, never a `5xx`) — losing autocomplete must never block the visitor from still using plain search (`GET /search`, unaffected).
- Suggestion count is capped server-side (10); not a client-configurable parameter in v1.

**Response** `400 Bad Request`: empty/whitespace-only `prefix`.

**Response** `401 Unauthorized`: no valid token presented.

**Latency contract (FR-011/SC-002)**: p95 < 300ms, target < 100ms, measured as server-side handler duration (excludes network transit to the client) — this is what the `ZREVRANGE` lookup (data-model.md) is sized to satisfy on the Redis-hit path; the Postgres fallback path (rare — only on a Redis miss/outage) is not held to this target, same as any other degrade-gracefully path. No fastembed round-trip is on this endpoint's path (autocomplete never touches the sparse/dense embedding infrastructure — that's `GET /search`'s job only).

## Frontend responsibilities (not part of the HTTP contract, noted for completeness)

- Debouncing (FR-005) and stale-response discarding (FR-006) happen client-side before/after these calls — the endpoints themselves are stateless and answer whatever request they receive, correctly, every time. Debounce/discard logic is what keeps the *volume* and *ordering* of calls sane; it is not something either endpoint enforces or assumes.
- The frontend additionally skips firing `GET /search/autocomplete` entirely once the typed text exceeds `SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN` (same value as the backend's `C`) — purely a network-round-trip optimization, since the backend would truncate+filter to the same effective result anyway; not a correctness requirement (data-model.md/research.md).
