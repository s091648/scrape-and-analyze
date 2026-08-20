---

description: "Task list template for feature implementation"
---

# Tasks: Article Search & Autocomplete

**Input**: Design documents from `/specs/023-article-search/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/search-api.md, quickstart.md

**Tests**: Every tasks.md MUST include at least one dedicated test phase (Constitution §III — mandatory regardless of spec silence). Test tasks below use:
- Frontend unit → `frontend/tests/unit/` (Vitest)
- Frontend E2E → `frontend/tests/integration/` (Playwright)
- Backend unit/integration → `backend/tests/`
- Scraper unit → `src/tests/unit/`

**Organization**: Tasks are grouped by user story (US1 = P1 search, US2 = P2 autocomplete, US3 = P3 debounce/responsiveness) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1/US2/US3); Setup/Foundational/Polish tasks have no story label

---

## Phase 1: Setup

- [x] T001 Remove obsolete `models/article_chunk.py` ORM model, its import in `models/__init__.py`, the two `ArticleChunk`-only assertions in `src/tests/unit/infrastructure/persistence/test_orm_models.py`, and correct the corresponding prose in `site/guide/architecture/db-schema.md` — **already completed this session** (research.md "Decision: `models/article_chunk.py` removed")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared backend scaffolding both US1 and US2 add their own endpoint/logic into, plus the new Postgres table US2's Redis fallback depends on — creating these once upfront avoids both stories racing to create the same files.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create `backend/schemas/search.py` with `SearchSuggestion` and `AutocompleteResponse` Pydantic models (importing the existing `PaginatedArticles`/`ArticleOut` from `backend/schemas/article.py` for `GET /search`'s response — data-model.md)
- [X] T003 Create `backend/routers/search.py` skeleton (empty `APIRouter(tags=["search"])`, no routes yet) and register it in `backend/main.py`'s `app.include_router(...)` calls, matching every other router's registration
- [X] T004 Create `backend/services/search_service.py` skeleton (empty module — US1 and US2 each add their own functions)
- [X] T005 [P] New Alembic migration `alembic/versions/26_add_search_terms_and_pg_trgm.py`: `intelligence.search_terms` table (`topic_id UUID`, `term TEXT`, `occurrence_count INTEGER`, `UNIQUE (topic_id, term)` — both the natural key and the upsert conflict target used by T031), `CREATE EXTENSION IF NOT EXISTS pg_trgm`, and a `pg_trgm` GIN index on `term` (data-model.md's "`intelligence.search_terms`" table — backs US2's Redis cache-aside fallback)

**Checkpoint**: Foundation ready — US1 and US2 implementation can now proceed independently (US3 additionally depends on US2's autocomplete wiring existing first, since debouncing has nothing to debounce without it)

---

## Phase 3: User Story 1 - Keyword search across articles (Priority: P1) 🎯 MVP

**Goal**: A visitor can type a keyword into the new search bar and get back matching articles — ranked via hybrid sparse+dense (RRF) relevance — with a clear no-results state.

**Independent Test**: Type a keyword known to appear in an article's title/content, submit, confirm returned results contain it and irrelevant articles are excluded; confirm a nonsense query returns an empty (not error) result; confirm clearing the search bar returns to normal browsing.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit tests for the sparse and dense SQL query builders (correct `<=>` operator for both, topic filter, tombstone exclusion, `GROUP BY`/`MIN(distance)` per-article dedup) and for the `_rrf_merge()` helper (correct `Σ 1/(k+rank+1)` scoring, stable ordering, handles a term present in only one of the two ranked lists) in `backend/tests/test_search_service.py`, mocking the DB session
- [X] T007 [P] [US1] Integration test for `GET /search` (real Postgres via existing integration conftest) in `backend/tests/integration/test_search.py`: matching query returns expected article, no-match query returns `{"items": [], "total": 0}` with `200`, empty/whitespace `q` returns `400`, missing token returns `401`, results respect `topic_id`
- [X] T008 [P] [US1] Frontend unit test confirming a stale (superseded) `GET /search` response is discarded — submit search A, then quickly submit search B before A's response resolves, assert only B's results ever render — in `frontend/tests/unit/articles-page-content-search.test.tsx` (component-level, not a standalone fetch-helper file — the AbortController wiring lives in `articles-page-content.tsx`'s effect, see T015)

### Implementation for User Story 1

- [X] T009 [US1] Add `SEARCH_EMBEDDING_ENDPOINT_URL` env var (default pointing at the existing `fastembed` compose service) to `.env.example` and `backend/config.py`, per Constitution IX's "no hardcoded values in `docker-compose.yml`, declare defaults only in `config.py`"
- [X] T010 [US1] Implement `embed_query(query: str) -> tuple[dict, list[float]]` — a single `httpx` POST to `SEARCH_EMBEDDING_ENDPOINT_URL`'s `/embed` (the real fastembed contract computes sparse+dense together in one call, not two separate endpoints — corrected during implementation after live testing against the real service) — in `backend/services/search_service.py`
- [X] T011 [US1] Implement `_rrf_merge(dense_rows, sparse_rows, k=60)` — Reciprocal Rank Fusion, ported from `chatbot-plugin-sdk`'s `_rrf_merge` algorithm (not the dependency — reimplemented locally per research.md) — in `backend/services/search_service.py`
- [X] T012 [US1] Implement `search_articles(db, query_sparse_vec, query_dense_vec, topic_id, page, size) -> PaginatedArticles` — runs both raw-SQL cosine queries from data-model.md (`vectors.article_chunks` `<=>` sparse and dense, joined through `vectors.articles`/`core.articles`, `merged_into_id IS NULL`, `top_k*3` candidates each), merges via `_rrf_merge`, returns the requested page — in `backend/services/search_service.py` (depends on T002, T011)
- [X] T013 [US1] Implement `GET /search` in `backend/routers/search.py`: `require_any_token` guard, trims/validates `q` (raises `ValidationError` on empty — never a raw `HTTPException`, per `017-exception-handling-guideline`), calls `search_articles_hybrid` (which internally calls `embed_query`), returns `PaginatedArticles` (depends on T003, T010, T012)
- [X] T014 [US1] Add OTel span + structured log (`structlog`/JSON logger per service) around the `GET /search` handler, per Constitution VI
- [X] T015 [US1] Create a client fetch helper for `GET /search` (`searchArticles`, via existing `apiFetch()` from `frontend/lib/api/client.ts`) in `frontend/lib/api/search.ts` (real location — `lib/api-fetch.ts` doesn't exist, the actual convention is `lib/api/<resource>.ts` re-exported via `lib/api/index.ts`); the `AbortController`/stale-response discarding itself lives in `articles-page-content.tsx`'s search effect, not in the fetch helper, so a superseded in-flight search request's response is discarded rather than rendered (FR-006 — closes the gap identified in `/speckit-analyze`: FR-006 covers stale *search* responses, not just autocomplete)
- [X] T016 [P] [US1] Create `SearchBar` component (text input + submit-on-Enter, no autocomplete yet) in `frontend/components/features/articles/search-bar.tsx`
- [X] T017 [P] [US1] Create `frontend/stories/SearchBar.stories.tsx` (real story convention — a top-level `frontend/stories/` directory, not colocated with the component; Constitution II — mandatory story for new `components/features/` component; cover default and "with query typed" states)
- [X] T018 [US1] Wire `SearchBar` into `frontend/app/articles/articles-page-content.tsx` and `frontend/app/articles/page.tsx`'s `buildArticlesQuery`: applying a search sets a `q` URL search param (matching the existing filter-param pattern) and replaces the rendered list with search results; clearing the search bar removes `q` and returns to the normal filtered/unfiltered list (FR-010) (depends on T015, T016)
- [X] T019 [P] [US1] Frontend unit test for `SearchBar`'s submit/clear behavior in `frontend/tests/unit/search-bar.test.tsx`

**Checkpoint**: User Story 1 is fully functional and independently testable — hybrid search works end-to-end with no autocomplete yet.

---

## Phase 4: User Story 2 - Autocomplete suggestions while typing (Priority: P2)

**Goal**: As the visitor types, a dropdown of real, corpus-derived suggested terms appears — matching the typed text anywhere within a term, not just as a prefix — ranked by how often they occur; selecting one runs a search. Survives a Redis outage via a Postgres fallback.

**Independent Test**: Type a partial term known to occur anywhere within a corpus term (not just at its start), confirm ranked real-term suggestions appear; confirm selecting one runs a search and closes the dropdown; confirm a prefix matching nothing returns an empty dropdown, not an error, including when the index hasn't been built yet or Redis is down.

### Tests for User Story 2

- [X] T020 [P] [US2] Unit test for the language-aware tokenizer — English split/lowercase, `jieba` segmentation for zh-TW content, `stopwordsiso` stopword filtering (both languages), minimum-length (≥2) filtering — in `src/tests/unit/modules/search/test_tokenizer.py`
- [X] T021 [P] [US2] Unit test for `RedisSearchIndexGateway` — `rebuild()` expands each term over every suffix's every prefix capped at `C=8` characters (verify `learning` → the full suffix-prefix set, verify the cap actually truncates a longer term), writes via a pipeline (not one round-trip per `ZADD`), swaps the built state in atomically (`SWAPDB`); `suggest()` returns ranked results via `ZREVRANGE`, truncating/post-filtering a query longer than `C`; both degrade gracefully (never raise, signal a miss) when Redis is unavailable, matching `CacheGateway`'s posture — in `src/tests/unit/shared/test_search_index_redis_gateway.py`
- [X] T022 [P] [US2] Unit test for the `intelligence.search_terms` Postgres repo — write path is one atomic transaction upserting on the `(topic_id, term)` unique constraint, read path's `ILIKE '%term%'` fallback query returns ranked-by-`occurrence_count` results — in `src/tests/unit/modules/search/test_search_term_repo.py`
- [X] T023 [P] [US2] Integration test for `GET /search/autocomplete` in `backend/tests/integration/test_search.py`: populated index returns ranked suggestions, empty/not-yet-built Redis index returns `{"suggestions": []}` with `200` (not an error), a query longer than `SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN` still returns correctly-filtered results, simulated Redis unavailability falls through to the Postgres `search_terms` table and still returns `200`, empty/whitespace `prefix` returns `400`

### Implementation for User Story 2

- [X] T024 [P] [US2] Add `jieba` and `stopwordsiso` to the `scraper` entry of `[dependency-groups]` in `pyproject.toml` (research.md — colocated with other scraper-only heavyweight deps)
- [X] T025 [P] [US2] Add `SEARCH_INDEX_REDIS_URL` (new dedicated logical Redis DB, e.g. db 2 — distinct from `REDIS_URL`/`CACHE_REDIS_URL`) and `SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN` (default `8`, matching the backend suffix-prefix cap `C`) env vars to `.env.example`, `src/config/settings.py`, and `backend/config.py`
- [X] T026 [P] [US2] Implement `SearchTerm` value object (`term: str`, `occurrence_count: int`) in `shared/search_index/search_term.py` — relocated here from `src/modules/search/domain/value_objects/` mid-implementation: `backend/services/search_service.py` imports `SearchTerm` directly, and `src/` is not copied into backend's production Docker image (`backend/Dockerfile` only copies `models/`, `shared/`, `backend/`) — caught via live testing against the real container, not by static review
- [X] T027 [P] [US2] Implement the language-aware tokenizer — title+content input, `jieba`+`stopwordsiso` for zh-TW, split+`stopwordsiso` for English, length ≥2 filter — in `src/modules/search/domain/services/tokenizer.py` (depends on T024)
- [X] T028 [P] [US2] Implement `SearchIndexGateway` Protocol in `shared/search_index/gateway.py` (`rebuild(topic_terms: dict[UUID, dict[str, int]])`, `suggest(topic_id, prefix, limit) -> list[SearchTerm]`) — mirrors `shared/cache/gateway.py`'s Protocol-first structure
- [X] T029 [US2] Implement `RedisSearchIndexGateway` in `shared/search_index/redis_gateway.py` — for each `(topic_id, term)`, expand into every prefix of every suffix capped at `C=8` chars and pipeline the `ZADD`s into a staging DB index, `SWAPDB` to go live, set `search:idx:rebuilt_at`; `suggest()` does `ZREVRANGE search:idx:{topic_id}:{prefix[:C]} 0 9`, post-filtering candidates against the full `prefix` when `len(prefix) > C`; never raises (data-model.md, research.md) (depends on T028)
- [X] T030 [US2] Implement the `intelligence.search_terms` repo in `shared/search_index/search_term_repo_impl.py` — **not** `src/modules/search/infrastructure/` as originally planned to fix the `/speckit-analyze`-flagged ambiguity: that reasoning ("only ever called from `RebuildSearchIndexUseCase`") turned out to be wrong once `suggest_terms()`'s Postgres fallback path was implemented — `backend/services/search_service.py` calls `find_matching()` directly on a Redis miss, so like `SearchTerm`/`RedisSearchIndexGateway` this must live in `shared/` (backend/ can't import `src/`, see T026's note) — `replace_all(topic_terms)` (one atomic transaction per rebuild, upserting on the `UNIQUE (topic_id, term)` constraint from T005) and `find_matching(topic_id, prefix, limit)` (the `pg_trgm`-backed `ILIKE` fallback query) (depends on T005)
- [X] T031 [US2] Implement `RebuildSearchIndexUseCase` in `src/modules/search/application/use_cases/rebuild_search_index_use_case.py`: queries `core.articles` (non-tombstoned) grouped by topic, tokenizes title+content, computes per-topic document-frequency counts, drops terms below `MIN_DOC_FREQ=2`, writes to the Postgres `search_terms` repo **first** (T030), then calls `SearchIndexGateway.rebuild(...)` (T029) **second** — write order per research.md's crash-safety reasoning (depends on T026, T027, T029, T030)
- [X] T032 [US2] Implement `SearchIndexRebuildHandler` in `src/modules/search/application/event_handlers/search_index_rebuild_handler.py` — `handle(event: PipelineCompletedEvent)` invoking `RebuildSearchIndexUseCase`, with start/finish/term-count structured logging matching `CacheInvalidationHandler`/`CacheWarmupHandler`'s existing log shape (depends on T031)
- [X] T033 [US2] Wire `SearchIndexRebuildHandler` into `src/bootstrap.py`'s `build_collection_pipeline()`, immediately after the existing `cache_warmup_handler` subscription (`src/bootstrap.py:423-438`): `event_bus.subscribe(PipelineCompletedEvent, with_span(SpanName.PIPELINE_COMPLETED_HANDLE, search_index_rebuild_handler.handle, _tracer))` (depends on T032)
- [X] T034 [US2] Implement `suggest_terms(topic_id, prefix, limit=10) -> AutocompleteResponse` in `backend/services/search_service.py`: tries `RedisSearchIndexGateway.suggest(...)` first; on a miss/error, falls back to the `search_terms` repo's `find_matching(...)` (T030) and writes the result back into Redis (cache-aside repopulation) (depends on T002, T029, T030)
- [X] T035 [US2] Implement `GET /search/autocomplete` in `backend/routers/search.py`: `require_any_token`, validates non-empty `prefix`, returns `AutocompleteResponse` (depends on T003, T034)
- [X] T036 [US2] Add OTel span + structured logging to the rebuild handler (T032) and the autocomplete endpoint (T035), per Constitution VI
- [X] T037 [P] [US2] Create `AutocompleteDropdown` component (renders ranked suggestions, click-to-select) in `frontend/components/features/articles/autocomplete-dropdown.tsx`
- [X] T038 [P] [US2] Create `frontend/stories/AutocompleteDropdown.stories.tsx` (real story convention, see T017; Constitution II — mandatory; cover default, populated, and empty states)
- [X] T039 [US2] Wire `AutocompleteDropdown` into `SearchBar`: fetch suggestions on input change (skipping the fetch entirely once the typed text exceeds `SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN` — contracts/search-api.md's frontend-guard note), selecting a suggestion runs a search via T018's search-apply path and closes the dropdown (Acceptance Scenario 2) (depends on T016, T018, T037)
- [X] T040 [P] [US2] Frontend unit test for `AutocompleteDropdown`'s render/select behavior in `frontend/tests/unit/autocomplete-dropdown.test.tsx`

**Checkpoint**: User Stories 1 AND 2 both work independently — hybrid search and Redis/Postgres-backed autocomplete are both functional (still without debouncing, i.e. one request per keystroke up to the length guard).

---

## Phase 5: User Story 3 - Fast, responsive typing experience (Priority: P3)

**Goal**: Autocomplete requests are throttled while typing, and only the response for the most-recently-typed text is ever shown.

**Independent Test**: Type a multi-character query at normal speed; confirm via network inspection that requests are throttled (not one per keystroke) and only the final typed text's suggestions ever render, including after a rapid type-then-delete.

### Tests for User Story 3

- [X] T041 [P] [US3] Unit test for `useDebouncedValue` (debounce timing, cleanup on unmount/rapid changes) in `frontend/tests/unit/use-debounced-value.test.ts`
- [X] T042 [P] [US3] Playwright E2E test: type a query at simulated normal speed, assert the number of `GET /search/autocomplete` network calls is well below the keystroke count, and the rendered dropdown matches only the final typed text (not an intermediate state) in `frontend/tests/integration/search-autocomplete.spec.ts`

### Implementation for User Story 3

- [X] T043 [US3] Implement `useDebouncedValue` hook in `frontend/hooks/use-debounced-value.ts`
- [X] T044 [US3] Wire debouncing and stale-response discarding (request-generation counter, so a late response for an already-superseded prefix is dropped) into `SearchBar`'s autocomplete trigger in `frontend/components/features/articles/search-bar.tsx` (depends on T039, T043)

**Checkpoint**: All three user stories are independently functional — the full feature (hybrid search, contains-matching autocomplete with Postgres fallback, debounced/responsive typing) is complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T045 [P] Add the `search.py` row to `CLAUDE.md`'s "Backend Routers" table (`/search` prefix, `require_any_token`)
- [X] T046 [P] Regenerate architecture diagrams (`make uml-backend`) and confirm `SearchIndexRebuildHandler` appears in the pipeline diagram per Constitution VIII's auto-discovery conventions
- [X] T047 Measure `GET /search/autocomplete`'s actual p95 latency against FR-011/SC-002's 300ms ceiling / 100ms target (e.g. a repeatable local script hitting the endpoint N times, or a note added to `backend/tests/integration/test_search.py` asserting a response-time ceiling) — closes the SC-002 coverage gap identified in `/speckit-analyze` (T021's tests only assert correctness, not timing)
- [X] T048 Run `specs/023-article-search/quickstart.md` end-to-end (index build, autocomplete incl. Redis-down fallback, hybrid search, browser walkthrough, regression check) and fix any gaps found
- [X] T049 [P] Confirm `uv sync --group scraper` (already run by `src/Dockerfile`) picks up the new `jieba`/`stopwordsiso` dependencies (T024) without further Docker image changes needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Already complete (T001)
- **Foundational (Phase 2)**: No dependencies beyond Setup — BLOCKS both US1 and US2
- **User Story 1 (Phase 3)**: Depends on Foundational only — fully independent of US2/US3
- **User Story 2 (Phase 4)**: Depends on Foundational only for its backend half (T024–T036); its frontend half (T037–T040) additionally depends on US1's `SearchBar`/search-apply path (T016, T018) existing to wire into
- **User Story 3 (Phase 5)**: Depends on US2's `AutocompleteDropdown` wiring (T039) — nothing to debounce without it
- **Polish (Phase 6)**: Depends on whichever stories are in scope for the release being complete

### Parallel Opportunities

- T002–T005 (Foundational) can run in parallel (different files)
- Within US1: T006/T007/T008 (tests) in parallel; T016/T017 (frontend component, story) in parallel
- Within US2: T020/T021/T022/T023 (tests) in parallel; T024–T028 in parallel (different files, no interdependency); T037/T038 in parallel
- US1 (Phase 3) and US2's backend half (T020–T036) can be worked on in parallel by different people once Foundational is done — they touch different functions within the shared `search_service.py`/`search.py` files, so coordinate merges there even though the *tasks* are independent
- Within US3: T041/T042 in parallel

---

## Parallel Example: User Story 1

```bash
# Tests
Task: "Unit tests for sparse/dense SQL query builders and RRF merge in backend/tests/test_search_service.py"
Task: "Integration test for GET /search in backend/tests/integration/test_search.py"
Task: "Frontend unit test for stale search-response discarding in frontend/tests/unit/articles-page-content-search.test.tsx"

# Frontend scaffolding
Task: "Create SearchBar component in frontend/components/features/articles/search-bar.tsx"
Task: "Create search-bar.stories.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (already done) → Phase 2: Foundational
2. Phase 3: User Story 1 — hybrid keyword+semantic search, no autocomplete
3. **STOP and VALIDATE**: run quickstart.md §3 (search only), confirm SC-001/SC-003
4. Deploy/demo if ready — search alone is already a complete, useful increment

### Incremental Delivery

1. Foundational → foundation ready
2. Add US1 → validate independently → deploy/demo (MVP)
3. Add US2 → validate independently (quickstart.md §1/§2, incl. simulated Redis outage) → deploy/demo
4. Add US3 → validate independently (quickstart.md's Network-tab check) → deploy/demo
5. Each story adds value without breaking the previous ones — US1 never depends on US2/US3 existing

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Constitution §III mandates all test tasks above — none are optional despite spec.md not explicitly requesting TDD
- Constitution §II mandates the two `.stories.tsx` tasks (T017, T038) for the two new `components/features/` components
- Verify tests fail before implementing (test-first within each story's task block)
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
