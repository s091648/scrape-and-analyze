# Implementation Plan: Async Event-Driven Collection Pipeline

**Branch**: `024-async-pipeline-refactor` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-async-pipeline-refactor/spec.md`

## Summary

Replace `build_collection_pipeline()`'s fully-synchronous per-article downstream chain (process→analyze→RAG→tag-normalize→translate, currently serialized one article at a time via `InMemoryEventBus.publish()`) with a native `asyncio` implementation where multiple articles' downstream processing runs concurrently, RAG ingestion for one article never blocks any other article, and two distinct fan-in barriers (text-complete, fully-complete) replace today's single `PipelineCompletedEvent`. Discovery, fetching, and the existing batched pre/post-fetch deduplication are ported to `async def` (so the whole run is one coroutine, top to bottom) but stay logically sequential/batched — no fan-out is introduced there. The `EventBus` port becomes an `async` Protocol so a future durable/cross-process implementation is a drop-in swap. `ResilientLLMService`/`ResilientEmbeddingService` gain a `ProviderSelector`-driven, non-blocking dispatch policy so concurrent callers spread across every registered model with spare capacity instead of queuing behind the single highest-priority one.

## Technical Context

**Language/Version**: Python 3.11 (unchanged) — native `asyncio`, no new async framework dependency.

**Primary Dependencies**:
- `SQLAlchemy>=2.0` — adds its async extension (`sqlalchemy.ext.asyncio`, already ships with core SQLAlchemy 2.x) + `asyncpg` driver, alongside (not replacing) the existing sync `psycopg2`-based engine other jobs keep using.
- `anthropic` SDK's `AsyncAnthropic`, `google-genai`'s `.aio` namespace, `httpx.AsyncClient` (replacing OpenRouter's `requests.post`) — all already-available async equivalents of the SDKs already in `pyproject.toml`; no new packages.
- `chatbot_plugin_sdk` — no changes needed. `IngestProcessor.ingest()` is already `async def`, and its dense/sparse embedding providers are already awaited internally (`await self._dense.embed(batch)` in `processors/ingest.py`), confirming the whole RAG ingestion path is async end-to-end already. This feature adds a new sibling builder, `build_async_rag_ingestion_service()`, using the already-existing `AsyncPgBackend` — `build_rag_ingestion_service()` (sync, `SyncPgBackend`) is left untouched because it's also called by the out-of-scope RAG-backfill job (`build_rag_backfill_pipeline()`, `bootstrap.py:787`); see research.md item 3.
- `pytest-asyncio` — already listed in the project's Technology Stack (constitution.md) for Python testing; no new test-tooling dependency.

**Storage**: PostgreSQL (unchanged) — this feature adds an async connection path (`asyncpg`) to the same database, it does not introduce a new datastore.

**Testing**: pytest + `pytest-asyncio` (`src/tests/unit/`, `src/tests/integration/`), run inside Docker per constitution Principle III/IV — unchanged test *infrastructure*, new *async* test patterns for the touched use cases/handlers.

**Target Platform**: Linux containers (scraper `app`/`job_service` Docker services), unchanged.

**Project Type**: Backend service (single Python project, `src/` DDD modules) — no frontend or API contract surface is touched by this feature.

**Performance Goals**: Not fixed as a specific number by the spec (see spec.md Assumptions) — SC-001/SC-004 are directional (RAG no longer dominates downstream wall-clock time; multiple low-quota models sustain higher combined throughput than the single top-priority one). Concrete concurrency limits (max simultaneous article tasks, max simultaneous model-pool dispatch) are tuning parameters decided during implementation, not spec-level requirements.

**Constraints**:
- Single process, single `asyncio` event loop (spec.md Assumptions — no multi-process/horizontal-scaling coordination in this feature).
- Discovery/fetch/batched-dedup phase boundary must not move (FR-003) — becomes `async def` for a uniform top-to-bottom coroutine, but stays sequential/non-concurrent internally.
- Repository/persistence changes scoped only to repositories the collection pipeline actually touches (article, analysis, translation ×3, tag, tag-group-definition, topic, failed-task) — see Research decision on why these need **new, separate async adapter classes** rather than converting the existing sync classes in place.
- OpenTelemetry span parent/child structure (constitution Principle VI) must survive the move from "one synchronous call stack per article" to "one `asyncio.Task` per article, with RAG as a further detached child task" — resolved in research.md via `asyncio`'s automatic `contextvars` propagation into new tasks.
- The UML auto-generation conventions (constitution Principle VIII) — event classes ending in `Event`/`...FailedEvent`, handler classes exposing `handle()`, wiring via `event_bus.subscribe(SomeEvent, handler.handle)` in `bootstrap.py`, the busiest `subscribe()`-calling function being auto-detected as the pipeline builder — must keep holding after the `EventBus` port and its wiring become async, so `make uml-backend` keeps working without `generate_uml.py` changes.

**Scale/Scope**: Touches `src/bootstrap.py::build_collection_pipeline()` (plus three new sibling builders — `build_async_llm_service()`, `build_async_rag_ingestion_service()`, and the async repository construction — added next to, not replacing, `build_llm_service()`/`build_rag_ingestion_service()`), `src/infrastructure/collection/collection_pipeline.py`, the `EventBus` port and its new `AsyncInMemoryEventBus` implementation (existing sync `InMemoryEventBus` untouched), new `AsyncResilientLLMService`/`AsyncResilientEmbeddingService` + `SlidingWindowStrategy.has_capacity()` (existing sync `ResilientLLMService`/`ResilientEmbeddingService` untouched), **new** `AsyncClaudeProvider`/`AsyncGeminiProvider`/`AsyncOpenRouterProvider` classes (existing sync provider classes untouched — see research.md item 3: they're called synchronously, with no `await`, from the untouched sync `ProviderHandler.analyze()`/`.translate()`/`.generate()` that `build_llm_service()`'s weekly-report/translation callers still use, so converting them in place would silently return unawaited coroutine objects to those callers), RAG ingestion wiring, and **new** async adapter implementations for the ~8 repositories the collection pipeline's downstream stages use. Explicitly does not touch: `build_weekly_pipeline()`, `build_metrics_refresh_pipeline()`, `build_dedup_reconciliation_pipeline()`, `build_rag_backfill_pipeline()`, `build_translation_pipeline()`, or any backend/frontend code — and, within `bootstrap.py`, does not modify `build_llm_service()` or `build_rag_ingestion_service()` themselves (research.md item 3).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. DDD (NON-NEGOTIABLE) | New `EventBus` async contract and async repository ports stay in `src/shared/application/ports/` and `src/modules/*/domain/repositories/` respectively; concrete async implementations stay in `src/infrastructure/`; all wiring stays in `src/bootstrap.py`. Domain entities/value objects touched by this feature remain plain `@dataclass` — no Pydantic introduced. | PASS |
| II. Atomic Frontend Architecture | Not applicable — no frontend code touched. | N/A |
| III. Test Discipline | New async code paths get `pytest-asyncio` unit tests in `src/tests/unit/` (no DB) and integration tests in `src/tests/integration/` (`@pytest.mark.integration`, isolated schema, run via Docker). Concurrency-specific behavior (FR-001, FR-002, FR-007, FR-013) needs tests that assert *interleaving*, not just end-state — flagged for `/speckit-tasks` to include explicitly, not left implicit. | PASS (tasks.md must include the concurrency-behavior test tasks per constitution's mandatory-test-phase rule) |
| IV. Docker-First | No change to how the scraper runs locally (`docker compose run app`/`job_service`) or in CI. | PASS |
| V. CI/CD Boundary | No change to deploy triggers or migration flow. This feature adds no new Alembic migration (no schema change — it's a runtime/orchestration change only). | PASS |
| VI. Observability | Span parent/child structure across the new per-article `asyncio.Task` boundaries is a first-class design concern here, not an afterthought — see research.md. Structured logging/metrics/Sentry behavior is unchanged (same events, same handlers, just async). | PASS (with explicit research task) |
| VII. Code Style & Quality | `providers.toml` referenced in the constitution's Technology Stack/Development Workflow sections is stale — CLAUDE.md documents provider config as DB-driven (`llm_providers` table) with no `providers.toml` in the repo. This plan follows CLAUDE.md/actual code, not the stale constitution text; the constitution's drift is out of scope for this feature to fix. | PASS (documented drift, not a violation of the DDD/style principles this feature actually touches) |
| VIII. UML Diagram Conventions | The async `EventBus.publish`/`subscribe` contract, `Event`/`...FailedEvent` naming, `handle()`-exposing handler classes, and `bootstrap.py`-centralized `subscribe()` wiring are all preserved by design (see Technical Context Constraints) so `generate_uml.py`'s structural inference keeps working unmodified. | PASS |
| IX. FastAPI Microservice Structure | Not applicable — no `backend/`/`chatbot-plugin/`/`fastembed` service code touched. | N/A |

No violations requiring justification — Complexity Tracking below documents one **accepted, deliberate cost** (parallel sync/async repository adapters) rather than a constitution violation.

**Post-Design Re-check** (after Phase 0/1): Design work surfaced one correctness-critical detail not visible from the spec alone — `CacheWarmupHandler` is subscribed strictly after `CacheInvalidationHandler` on the same event (`bootstrap.py:443-448`) because it depends on that ordering, not just presentation in the monitoring waterfall. This could have become a Principle VI (Observability)/silent-correctness-regression risk if the `EventBus` port had been designed to fan out sibling handlers concurrently via `asyncio.gather`. Resolved during design, not deferred: `contracts/event-bus-port.md` now specifies strictly sequential, `subscribe()`-order handler dispatch within one `publish()` call as a hard contract requirement, with a dedicated regression test called out in quickstart.md. No other new risks surfaced. All rows above still PASS.

## Project Structure

### Documentation (this feature)

```text
specs/024-async-pipeline-refactor/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── event-bus-port.md
│   ├── provider-selector-port.md
│   └── async-repository-ports.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── shared/application/ports/
│   └── event_bus.py                      # EventBus Protocol → async publish/subscribe
├── infrastructure/
│   ├── shared/events/
│   │   └── in_memory_event_bus.py        # AsyncInMemoryEventBus implementation
│   ├── intelligence/llm/
│   │   ├── resilient_llm_service.py      # + new AsyncResilientLLMService/AsyncResilientEmbeddingService classes; existing sync ResilientLLMService/ResilientEmbeddingService untouched
│   │   ├── rate_limit/
│   │   │   ├── sliding_window_strategy.py # + non-blocking has_capacity()/try_acquire()
│   │   │   └── provider_selector.py       # NEW — mirrors queue_selector.py's shape
│   │   └── providers/
│   │       ├── claude_provider.py         # unchanged (sync, still used by build_llm_service())
│   │       ├── async_claude_provider.py   # NEW — AsyncAnthropic
│   │       ├── gemini_provider.py         # unchanged (sync)
│   │       ├── async_gemini_provider.py   # NEW — genai .aio
│   │       ├── openrouter_provider.py     # unchanged (sync)
│   │       └── async_openrouter_provider.py # NEW — httpx.AsyncClient
│   ├── collection/
│   │   └── collection_pipeline.py        # async def run(); per-article asyncio.Task fan-out; two-barrier gather
│   └── persistence/
│       ├── database.py                    # + get_async_sessionmaker() (asyncpg engine, separate from sync one)
│       └── {shared,collection,intelligence}/*_async_repo_impl.py  # NEW async adapters, alongside existing sync ones
└── bootstrap.py                           # build_collection_pipeline() becomes async; other build_* functions untouched

tests/
├── src/tests/unit/          # pytest-asyncio unit tests, no DB
└── src/tests/integration/   # pytest-asyncio + @pytest.mark.integration, isolated schema
```

**Structure Decision**: Single project (this is the existing `src/` DDD scraper service; no new service, no frontend/backend split needed). New files are added alongside existing ones following the same directory layout already established by the constitution's DDD principle — async repository adapters live as sibling files next to their sync counterparts (e.g. `article_repo_impl.py` next to a new `article_async_repo_impl.py`), not in a separate parallel tree, so the existing `_repo_impl` filename convention (relied on by `generate_uml.py`, constitution Principle VIII) keeps classifying them correctly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Separate async repository adapter classes (e.g. `AsyncSqlAlchemyTopicRepository` alongside the existing `SqlAlchemyTopicRepository`) instead of converting the existing sync classes to `async def` in place | Several of the repositories the collection pipeline's downstream stages use are **shared with other, out-of-scope pipelines** — confirmed concretely for `SqlAlchemyTopicRepository`, constructed and used in both `build_collection_pipeline()` (`bootstrap.py:285`) and `build_weekly_pipeline()` (`bootstrap.py:606`). Converting the shared class's methods to `async def` would break every other caller (weekly report, and potentially others depending on final per-repo audit in research.md), which spec.md's Assumptions explicitly rule out touching. | Converting the shared sync repos in place was rejected because it would silently expand this feature's blast radius into every other job that reuses them — violating the spec's own scope boundary. Migrating those other jobs to async too was rejected as explicitly out of scope by spec.md. The accepted cost is near-duplicate SQL logic between a repo's sync and async adapter for the handful of repositories this pipeline touches (~8) — bounded, and isolated behind the same domain-layer repository Protocol pattern the DDD principle already mandates, so it doesn't violate DDD layering, it just means two adapters implement one port instead of one. |
| Same isolation policy applied to `build_rag_ingestion_service()` → a new sibling `build_async_rag_ingestion_service()`, leaving the original untouched | `build_rag_ingestion_service()` (`bootstrap.py:95`) is also shared with the out-of-scope `build_rag_backfill_pipeline()` (`bootstrap.py:787`) — caught during planning, after the repository instance of this same risk had already been found. See research.md item 3. | Same reasoning as the repository row above — converting in place breaks an out-of-scope caller; the accepted cost is a second, small builder function with some shared embedding-provider construction logic factored out, not the whole function duplicated. |
| Same isolation policy applied two more times: `build_llm_service()`/`ResilientLLMService`/`ResilientEmbeddingService` → new `build_async_llm_service()`/`AsyncResilientLLMService`/`AsyncResilientEmbeddingService`; `ClaudeProvider`/`GeminiProvider`/`OpenRouterProvider` → new `AsyncClaudeProvider`/`AsyncGeminiProvider`/`AsyncOpenRouterProvider` | `build_llm_service()` is shared by `build_weekly_pipeline()` and `build_translation_pipeline()` (both out of scope) in addition to `build_collection_pipeline()` — the single most-shared piece of code this feature touches. The provider classes are one layer further: even though `build_llm_service()` itself is untouched, converting the provider classes it constructs would still silently break its sync consumers (an untouched sync `ProviderHandler` calling an now-async provider method with no `await`). See research.md item 3. | Same reasoning as the two rows above, applied twice more because the sharing goes two layers deep here (builder function, then the classes it constructs, then the classes *those* construct). The accepted cost scales accordingly — this is the largest slice of the "parallel sync/async" cost in this feature — but each new class is a thin, mechanical mirror of its sync counterpart, not a redesign. |
