# Implementation Plan: Article Search & Autocomplete

**Branch**: `023-article-search` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-article-search/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a search bar with real-content autocomplete to the articles page. Search runs **hybrid retrieval** — both the already-populated `vectors.article_chunks.sparse_vector` (SPLADE, keyword-shaped) and `dense_vector` (semantic) columns, queried via two raw-SQL cosine queries and merged with Reciprocal Rank Fusion — no new search engine (ElasticSearch/OpenSearch rejected as unnecessary infra at this scale; both vector columns and their HNSW indexes already exist from the RAG ingestion pipeline, so this is new query code, not new infrastructure). Autocomplete is served from a dedicated Redis DB index holding a suffix-expanded prefix→ranked-terms structure (matching anywhere within a term, not prefix-only), rebuilt from scratch each scheduled scrape cycle by a new `PipelineCompletedEvent` handler (not a hardcoded step in `main.py`, to match the existing cache-invalidation/warmup handler pattern), backed by a compact Postgres table (`intelligence.search_terms`) that the autocomplete endpoint falls back to on a Redis miss/outage. As a prerequisite cleanup, the stale `models/article_chunk.py` ORM model (never used for I/O, diverged from the live table shape) has already been removed — chunk reads/writes go through raw SQL / the existing `chatbot-plugin-sdk` write path instead.

## Technical Context

**Language/Version**: Python 3.11 (`src/`, `backend/`); TypeScript 5.x / React 19, strict mode (`frontend/`)

**Primary Dependencies**: FastAPI (`backend/routers/search.py`), SQLAlchemy 2.0 (raw `text()` queries against `vectors.article_chunks`/`vectors.articles`/`core.articles` — no ORM model for the vectors-schema tables, per Decision in research.md), `httpx` (query-time sparse + dense embedding calls to the `fastembed` service), `redis` (sync client, matching `shared/cache/redis_gateway.py`'s existing precedent), `jieba` + `stopwordsiso` (new scraper-only deps for autocomplete tokenization), Next.js 16 App Router + Shadcn/UI (frontend search bar/autocomplete dropdown)

**Storage**: PostgreSQL 15 + pgvector (`vectors.article_chunks.sparse_vector SPARSEVEC(30522)` + `dense_vector VECTOR(768)`, both already populated, both already HNSW-indexed — read-only reuse for search, no schema change there) **plus one new table**, `intelligence.search_terms` (new Alembic migration — compact autocomplete term list + `pg_trgm` extension, backs the Redis cache-aside fallback; see data-model.md); Redis (new dedicated logical DB index for the autocomplete term index, alongside the existing `REDIS_URL` db 0 and `CACHE_REDIS_URL` db 1 — see research.md "Decision: Redis DB allocation")

**Testing**: pytest (`src/tests/unit/`, `backend/tests/`) via Docker per Constitution Principle III; Vitest (`frontend/tests/unit/`) + Playwright (`frontend/tests/integration/`)

**Target Platform**: Linux server (Railway), Docker Compose for local dev — no new service/container (reuses the existing `postgres` and `redis` services)

**Project Type**: Web application — existing three-service architecture (`src/` scraper, `backend/` FastAPI, `frontend/` Next.js), extended with a new `src/modules/search/` bounded context, a new `backend/routers/search.py` + `backend/services/search_service.py`, and search-bar UI added to the existing articles page

**Performance Goals**: Autocomplete p95 < 300ms, target < 100ms (FR-011/SC-002); search results returned fast enough to feel like a normal paginated list fetch (no explicit numeric target beyond FR-011 — search itself is not autocomplete-latency-critical, though it now does two embedding calls + two SQL queries per request for the hybrid RRF merge)

**Constraints**: No new search-engine tech stack (FR/Assumptions — ElasticSearch/OpenSearch explicitly rejected); autocomplete index is rebuilt wholesale each scheduled scrape cycle, not incrementally updated (FR-008); both guest and authenticated visitors supported (`require_any_token`, FR-012); search/autocomplete scoped to the visitor's current topic (FR-009)

**Scale/Scope**: Side-project scale — single-digit-thousands of articles, not a high-QPS public search engine; sized accordingly (e.g. rebuilding the entire term index from scratch each cycle is acceptable at this volume)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance |
|---|---|
| I. DDD (NON-NEGOTIABLE) | New bounded context `src/modules/search/` with domain (`SearchTerm` VO, `SearchIndexGateway` port interface), application (`RebuildSearchIndexUseCase`, `SearchIndexRebuildHandler`), infrastructure (`search_term_repo_impl.py` under `src/modules/search/infrastructure/` for the Postgres `search_terms` fallback table). `RedisSearchIndexGateway` itself lives under `shared/search_index/` (not `src/modules/search/infrastructure/`) so `backend/` can also depend on it without reaching into `src/modules/*` — mirrors `shared/cache/`'s existing split. No domain-layer dependency on Redis/Postgres specifics. |
| II. Atomic Frontend | New `SearchBar` + `AutocompleteDropdown` land in `components/features/articles/` (feature organism, articles-specific); a new `useDebouncedValue` hook goes in `frontend/hooks/` (matching `use-pagination.ts`'s existing location — no reusable debounce hook exists today, only an inline `setTimeout`/`clearTimeout` ref pattern in `knowledge-graph.tsx`). Storybook stories required for both new `components/features/` components. |
| III. Test Discipline | Unit tests for tokenization/ranking logic (`src/tests/unit/`), the new backend service/router (`backend/tests/`), and frontend debounce/dropdown behavior (Vitest) are mandatory per Principle III regardless of spec silence — sized in tasks.md. |
| IV. Docker-First | No new service or image — reuses the existing `redis` and `postgres` `docker compose` services already running. |
| V. CI/CD Boundary | No deploy-topology change. The index-rebuild handler runs inside the existing scraper pipeline's process (`app`/scheduled runner), not a new Railway service. |
| VI. Observability | New router endpoints get OTel spans + structured logs per existing FastAPI microservice convention; the rebuild handler logs start/finish/term-count like other `PipelineCompletedEvent` handlers (`CacheInvalidationHandler`, `CacheWarmupHandler`). |
| VII. Code Style | Pydantic schemas for the two new endpoints' request/response shapes (`backend/schemas/search.py`); raw SQL via parameterized `text()` — never string-interpolated — for the `vectors.article_chunks` query, consistent with why that table has no ORM model. |
| VIII. UML Conventions | `src/modules/search/` gets its own context tab automatically (directory convention); `SearchIndexRebuildHandler` follows the `handle()` + `UpperCamelCase` + `bootstrap.py` `event_bus.subscribe(PipelineCompletedEvent, handler.handle)` convention so it's picked up by the pipeline diagram like `CacheInvalidationHandler`/`CacheWarmupHandler` already are. |
| IX. FastAPI Microservice Structure | `backend/routers/search.py` (routes only) + `backend/services/search_service.py` (business logic, no HTTP/config knowledge) — same split as every existing router/service pair. |

No violations requiring Complexity Tracking justification.

**Post-Phase-1 re-check**: research.md and data-model.md confirm the design still fits every row above — no new service/container, no new ORM model (raw SQL retained, matching the existing rationale), the rebuild handler slots into the existing `PipelineCompletedEvent` mechanism rather than inventing a new one, and Redis usage adds one new logical DB index rather than a new deployment. Gate remains passed.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
shared/
└── search_index/                      # NEW — mirrors shared/cache/ split (both src/ and backend/ depend on this)
    ├── search_term.py                 # SearchTerm VO (term, occurrence_count) — moved here (not
    │                                   #   src/modules/search/domain/) since backend/ imports it
    │                                   #   directly and src/ is NOT copied into backend's prod image
    ├── gateway.py                     # SearchIndexGateway Protocol (rebuild, suggest)
    ├── redis_gateway.py               # RedisSearchIndexGateway impl — flattened prefix→ZSET
    └── search_term_repo_impl.py       # SqlAlchemySearchTermRepository — same reason as search_term.py;
                                        #   backend/services/search_service.py calls find_matching()
                                        #   directly on a Redis miss

src/modules/search/                    # NEW bounded context — scraper-only concerns
├── domain/
│   └── services/
│       └── tokenizer.py               # language-aware tokenization (en / jieba+stopwordsiso zh-TW)
├── application/
│   ├── use_cases/
│   │   └── rebuild_search_index_use_case.py
│   └── event_handlers/
│       └── search_index_rebuild_handler.py   # subscribes to PipelineCompletedEvent
└── infrastructure/                    # (empty — everything backend/ also needs lives in shared/, see above)

backend/
├── routers/
│   └── search.py                      # NEW — GET /search, GET /search/autocomplete
├── services/
│   └── search_service.py              # NEW — sparse-vector query (raw SQL) + autocomplete lookup
└── schemas/
    └── search.py                      # NEW — Pydantic request/response models

frontend/
├── app/articles/
│   ├── page.tsx                       # existing — no structural change
│   └── articles-page-content.tsx      # MODIFIED — mounts <SearchBar />, applies search state
├── components/features/articles/
│   ├── search-bar.tsx                 # NEW
│   └── autocomplete-dropdown.tsx      # NEW
├── stories/                           # real story convention — top-level, not colocated
│   ├── SearchBar.stories.tsx          # NEW (Constitution II — mandatory story)
│   └── AutocompleteDropdown.stories.tsx  # NEW (Constitution II — mandatory story)
├── lib/api/
│   └── search.ts                      # NEW — searchArticles, fetchAutocompleteSuggestions (real convention: lib/api/<resource>.ts, not lib/api-fetch.ts)
└── hooks/
    └── use-debounced-value.ts         # NEW

src/tests/unit/modules/search/         # NEW
src/tests/unit/shared/                 # extended — test_search_index_redis_gateway.py, test_search_term_repo.py
backend/tests/                         # extended — test_search_service.py, integration/test_search.py
frontend/tests/unit/                   # extended — search-bar, autocomplete-dropdown, use-debounced-value, articles-page-content-search
```

**Structure Decision**: Web application (Option 2 shape), extended in-place — this feature adds one new bounded context (`src/modules/search/`) following the existing DDD module layout, one new shared infrastructure package (`shared/search_index/`, mirroring the precedent set by `shared/cache/` for exactly the same reason: both the scraper pipeline *writer* and the backend API *reader* need the same Redis access logic without backend reaching into `src/modules/*`), one new router+service+schema trio in `backend/` (matching every existing router), and new feature components in `frontend/components/features/articles/` plus a new shared hook in `frontend/hooks/`. No new top-level service, container, or project is introduced.

## Complexity Tracking

N/A — no Constitution Check violations (see table above).
