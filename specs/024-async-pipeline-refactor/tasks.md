# Tasks: Async Event-Driven Collection Pipeline

**Input**: Design documents from `/specs/024-async-pipeline-refactor/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included per user story per constitution §III (mandatory, not optional). Ordering within each phase is implementation-first, tests-second — this project does not use TDD (write-test-first-and-watch-it-fail); tests verify behavior after implementation, per established team practice.

**A recurring, load-bearing constraint across almost every phase below**: `src/bootstrap.py` has several functions/classes shared with pipelines explicitly out of scope for this feature (`build_weekly_pipeline()`, `build_metrics_refresh_pipeline()`, `build_dedup_reconciliation_pipeline()`, `build_rag_backfill_pipeline()`, `build_translation_pipeline()`). Confirmed shared: `build_llm_service()`/`ResilientLLMService`/`ResilientEmbeddingService`/`ClaudeProvider`/`GeminiProvider`/`OpenRouterProvider` (weekly-report, translation), `build_rag_ingestion_service()` (RAG-backfill), `SqlAlchemyTopicRepository` (weekly-report), and by policy every other repository this pipeline touches (research.md item 3, applied uniformly rather than repo-by-repo). **Every task below that touches one of these adds a new, separate async sibling — it never edits the existing shared sync code's behavior or signatures.** The one exception is the `EventBus` Protocol (`src/shared/application/ports/event_bus.py`), which every pipeline builder consumes through its own separate concrete instance — safe to edit in place (research.md item 4's rationale).

## Path Conventions

Single project (existing `src/` DDD scraper service). Test paths: `src/tests/unit/` (no DB), `src/tests/integration/` (`@pytest.mark.integration`, isolated schema) — both run via `make test`/`make test-integration` (Docker), per constitution Principle III/IV.

---

## Phase 1: Setup

- [ ] T001 Add `asyncpg` as an explicit dependency in the `scraper` group of `pyproject.toml` (already a transitive dependency via `chatbot-plugin-sdk`, but this pipeline's own code now imports it directly for `create_async_engine`) — then run `uv lock` to update `uv.lock`
- [ ] T002 Add `httpx` as an explicit dependency in the `llm` group of `pyproject.toml` (needed by the new `AsyncOpenRouterProvider`; currently only declared in `backend`/`dev` groups) — then run `uv lock`

**Checkpoint**: Dependencies available inside the `app`/`job_service`/`test_service` Docker images on next `docker compose build`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Async infrastructure every user story's work depends on. No user story task can be meaningfully tested until this phase is complete.

### 2a. Async database session

- [ ] T003 Add `get_async_sessionmaker()` to `src/infrastructure/persistence/database.py` — builds an `asyncpg`-backed `create_async_engine(...)` + `async_sessionmaker(...)` once (module-level singleton, mirroring the existing sync `get_session()`'s `_engine`/`_SessionLocal` pattern), entirely separate from the existing sync engine
- [ ] T004 [P] Unit test: two calls into `get_async_sessionmaker()`'s factory produce distinct `AsyncSession` instances (never the same object) in `src/tests/unit/test_database_async.py`

### 2b. `EventBus` async port (safe to edit in place — research.md item 4)

- [ ] T005 Change `EventBus.subscribe`/`EventBus.publish` to `async def` in `src/shared/application/ports/event_bus.py`, per contracts/event-bus-port.md's exact guarantees (sequential, `subscribe()`-order handler dispatch within one `publish()` call — **not** `asyncio.gather` across sibling handlers)
- [ ] T006 Implement `AsyncInMemoryEventBus` in `src/infrastructure/shared/events/in_memory_event_bus.py`, as a new class alongside the existing sync `InMemoryEventBus` (which stays untouched — still used by every other pipeline builder)
- [ ] T007 [P] Unit test: `AsyncInMemoryEventBus.publish()` awaits handlers for the same event type strictly in `subscribe()`-call order (assert call-order via a shared mutable list two handlers append to) in `src/tests/unit/test_in_memory_event_bus.py`
- [ ] T008 [P] Unit test: one handler raising does not prevent the remaining handlers (for the same event) from still being awaited, in `src/tests/unit/test_in_memory_event_bus.py`
- [ ] T009 [P] Unit test: `publish()` calls for two *different* event instances run concurrently (via `asyncio.gather` of two `publish()` calls, one handler with an injected `asyncio.sleep`, asserting overlap) in `src/tests/unit/test_in_memory_event_bus.py`

### 2c. Async repository ports (new adapters; existing sync repos/Protocols untouched)

- [ ] T010 [P] Define `AsyncArticleRepository` Protocol (save-only — `find_analyzed_url_hashes` stays on the existing sync `ArticleRepository`, used only by the still-batched fetch/dedup phase) in `src/modules/collection/domain/repositories/article_repository.py`, implement `AsyncSqlAlchemyArticleRepository` in `src/infrastructure/persistence/shared/article_async_repo_impl.py`
- [ ] T011 [P] Define `AsyncAnalysisRepository` Protocol in `src/modules/intelligence/domain/repositories/analysis_repository.py`, implement `AsyncSqlAlchemyAnalysisRepository` in `src/infrastructure/persistence/intelligence/analysis_async_repo_impl.py`
- [ ] T012 [P] Define `AsyncAnalysesTranslationRepository` Protocol, implement `AsyncSqlAlchemyAnalysesTranslationRepository` in `src/infrastructure/persistence/intelligence/analyses_translation_async_repo_impl.py`
- [ ] T013 [P] Define `AsyncTagTranslationRepository` Protocol, implement `AsyncSqlAlchemyTagTranslationRepository` in `src/infrastructure/persistence/intelligence/tag_translation_async_repo_impl.py`
- [ ] T014 [P] Define `AsyncArticleTranslationRepository` Protocol, implement `AsyncSqlAlchemyArticleTranslationRepository` in `src/infrastructure/persistence/intelligence/article_translation_async_repo_impl.py`
- [ ] T015 [P] Define `AsyncTagRepository` Protocol, implement `AsyncSqlAlchemyTagRepository` in `src/infrastructure/persistence/intelligence/tag_async_repo_impl.py`
- [ ] T016 [P] Define `AsyncTagGroupDefinitionRepository` Protocol, implement `AsyncSqlAlchemyTagGroupDefinitionRepository` in `src/infrastructure/persistence/intelligence/tag_group_definition_async_repo_impl.py`
- [ ] T017 [P] Define `AsyncTopicRepository` Protocol, implement `AsyncSqlAlchemyTopicRepository` in `src/infrastructure/persistence/shared/topic_async_repo_impl.py` — this one is the confirmed-shared case (`SqlAlchemyTopicRepository` also used by `build_weekly_pipeline()`), do not touch the existing class
- [ ] T018 [P] Define `AsyncFailedTaskRepository` Protocol, implement `AsyncSqlAlchemyFailedTaskRepository` in `src/infrastructure/persistence/shared/failed_task_async_repo_impl.py`
- [ ] T019 [P] Integration tests: each new async repository's save/read round-trips correctly against the isolated `test_integration` schema, in `src/tests/integration/test_async_repositories.py` (depends on T010-T018)

### 2d. Async LLM provider classes (new siblings; existing sync providers untouched)

- [ ] T020 [P] Implement `AsyncClaudeProvider` (using `anthropic.AsyncAnthropic`) in `src/infrastructure/intelligence/llm/providers/async_claude_provider.py`, mirroring `ClaudeProvider`'s `analyze`/`translate`/`generate` method set as `async def`
- [ ] T021 [P] Implement `AsyncGeminiProvider` (using `genai.Client(...).aio`) in `src/infrastructure/intelligence/llm/providers/async_gemini_provider.py`
- [ ] T022 [P] Implement `AsyncOpenRouterProvider` (using `httpx.AsyncClient`, replacing `requests.post`) in `src/infrastructure/intelligence/llm/providers/async_openrouter_provider.py`
- [ ] T023 [P] Unit tests for each new async provider (mocked async client) in `src/tests/unit/test_async_claude_provider.py`, `test_async_gemini_provider.py`, `test_async_openrouter_provider.py`

### 2e. `AsyncResilientLLMService`/`AsyncResilientEmbeddingService` (new classes; existing sync services untouched)

- [ ] T024 Implement `AsyncProviderHandler`/`AsyncResilientLLMService` (async `analyze`/`translate`/`generate`, priority-fallback dispatch identical to today's sync behavior — the `ProviderSelector` upgrade lands in Phase 6/US4, not here) in `src/infrastructure/intelligence/llm/resilient_llm_service.py`, alongside the existing sync classes
- [ ] T025 Implement `AsyncEmbeddingProviderHandler`/`AsyncResilientEmbeddingService` (same pattern) in the same file
- [ ] T026 Add `build_async_llm_service(session)` to `src/bootstrap.py`, alongside the existing `build_llm_service()` — constructs `AsyncClaudeProvider`/`AsyncGeminiProvider`/`AsyncOpenRouterProvider` (T020-T022) wrapped in `AsyncProviderHandler`s, reusing the same `load_active_providers`/`load_active_embedding_providers` DB reads (read-only, safe to share) as the sync path
- [ ] T027 [P] Unit tests for `AsyncResilientLLMService`/`AsyncResilientEmbeddingService`'s fallback-on-`RateLimitExhausted` behavior (mirroring the existing sync test suite, adapted to `pytest-asyncio`) in `src/tests/unit/test_async_resilient_llm_service.py`

### 2f. RAG async wiring (new sibling builder; existing sync RAG wiring untouched)

- [ ] T028 Add `build_async_rag_ingestion_service()` to `src/bootstrap.py`, alongside the existing `build_rag_ingestion_service()` — uses `AsyncPgBackend` (already exists in `chatbot_plugin_sdk`) instead of `SyncPgBackend`, and awaits `IngestProcessor.ingest()` natively (no `asyncio.run()` wrapper). Factor the dense/sparse embedding-provider construction (`build_dense_provider`/`build_sparse_provider` calls and the missing-config/SDK-not-installed handling) into a small shared helper both builders call, since that part is identical either way
- [ ] T029 [P] Convert `IngestArticleForRagUseCase` and `RagIngestionHandler` to `async def` in `src/modules/intelligence/application/use_cases/ingest_article_for_rag.py` and `src/modules/intelligence/application/event_handlers/rag_ingestion_handler.py` — these are only ever constructed inside `build_collection_pipeline()`, not shared, safe to convert directly
- [ ] T030 [P] Unit test confirming RAG ingestion is awaited through the async path (mocked `AsyncPgBackend`/`IngestProcessor`) in `src/tests/unit/test_rag_ingestion_handler.py`

**Checkpoint**: All async building blocks exist and are unit-tested in isolation. No pipeline orchestration wired up yet — that starts in Phase 3.

---

## Phase 3: User Story 1 - A scheduled run finishes without one slow article blocking every other article (Priority: P1) 🎯 MVP

**Goal**: Multiple articles' downstream processing (analyze, translate, RAG) runs concurrently; RAG ingestion for one article never blocks another article's progress.

**Independent Test**: Run the pipeline against a batch with at least one RAG-eligible article; confirm more than one article's downstream processing is in flight at once, and an artificially slow RAG ingestion doesn't delay other articles' analyze/translate.

### Implementation for User Story 1

- [ ] T031 [US1] Convert `CollectionPipeline.run()` to `async def` in `src/infrastructure/collection/collection_pipeline.py` — `await` the (unchanged, still-sequential) discover/fetch/batched-dedup calls; behavior of that phase does not change, only its calling convention (research.md item 9)
- [ ] T032 [US1] Replace the per-article `for article in results: event_bus.publish(...)` loop with one `asyncio.Task` per article in `src/infrastructure/collection/collection_pipeline.py` — each task opens its own `AsyncSession` (via T003's factory), constructs its own async repositories (T010-T018) and use cases, and awaits its own chain of `publish()` calls on the `AsyncInMemoryEventBus` (T006)
- [ ] T033 [US1] Convert `ProcessScrapedArticleUseCase`, `ArticleScrapedHandler`, `AnalyzeArticleUseCase`, `ArticleProcessedHandler`, `NormalizeTagsUseCase`, `TagNormalizationHandler`, `TranslateArticleUseCase`, `TranslateTagsUseCase`, `TranslateArticleBodyUseCase`, `AnalysisCompletedHandler` to `async def` methods, threaded through with the per-task `AsyncSession`/async repos from T032 instead of the previous single shared session — files under `src/modules/collection/application/` and `src/modules/intelligence/application/`
- [ ] T034 [US1] In the handler that dispatches RAG ingestion (subscribed to `ArticleProcessedEvent`), replace the inline `await rag_ingestion_handler.handle(event)` with `asyncio.create_task(rag_ingestion_handler.handle(event))`, registering the created task on a run-level RAG-task collector (a simple `list[asyncio.Task]` passed down from `CollectionPipeline.run()`) instead of awaiting it — implemented in `src/infrastructure/collection/collection_pipeline.py`
- [ ] T035 [US1] Update `src/entrypoints/cli/main.py` to `asyncio.run(pipeline.run())`, replacing the direct synchronous call
- [ ] T036 [US1] Update `build_collection_pipeline()` in `src/bootstrap.py` to wire everything from Phase 2 together: `build_async_llm_service()`, `build_async_rag_ingestion_service()`, `AsyncInMemoryEventBus()`, the async repository constructors, and the new async use cases/handlers from T033-T034 — this function becomes `async def` (or returns an awaitable pipeline whose `.run()` is async; exact shape decided here)

### Tests for User Story 1

- [ ] T037 [P] [US1] Integration test: a batch of N articles' downstream processing overlaps in wall-clock time (assert via per-article start/end timestamps or injected delays) in `src/tests/integration/test_collection_pipeline_concurrency.py`
- [ ] T038 [P] [US1] Integration test: one article's artificially-slowed RAG ingestion does not delay another article's analyze/translate completion, in `src/tests/integration/test_collection_pipeline_concurrency.py`
- [ ] T039 [P] [US1] Unit test: no two concurrently-running article tasks ever hold the same `AsyncSession` instance (assert distinct object identity across tasks) in `src/tests/unit/test_collection_pipeline_sessions.py`

**Checkpoint**: User Story 1 is fully functional and independently testable — this is the MVP. `CollectionPipeline.run()` now processes articles concurrently end-to-end, though completion notification/search-index timing still matches today's single-barrier behavior until Phase 4/5 land.

---

## Phase 4: User Story 2 - Freshly scraped articles become searchable without waiting on RAG (Priority: P2)

**Goal**: Search-index rebuild and cache refresh fire once every article's text stage (scrape+analyze+translate) has settled — without waiting on RAG.

**Independent Test**: Run a batch with RAG-eligible articles; artificially slow RAG for one; confirm search index/cache refresh completes, reflecting every article's text content, before that article's RAG ingestion finishes.

### Implementation for User Story 2

- [ ] T040 [US2] Add `TextPipelineCompletedEvent` (ends in `Event` per constitution Principle VIII) in `src/modules/collection/application/events/`
- [ ] T041 [US2] In `CollectionPipeline.run()` (`src/infrastructure/collection/collection_pipeline.py`), await Barrier 1: `results = await asyncio.gather(*(article_tasks), return_exceptions=True)` (settle semantics per Clarifications/research.md item 6), then `await event_bus.publish(TextPipelineCompletedEvent(...))`
- [ ] T042 [US2] In `src/bootstrap.py`, move `SearchIndexRebuildHandler`, `CacheInvalidationHandler`, `CacheWarmupHandler` subscriptions from `PipelineCompletedEvent` to `TextPipelineCompletedEvent` — preserve the existing `CacheInvalidationHandler` → `CacheWarmupHandler` subscribe-order (the correctness dependency documented at `bootstrap.py:443-448`)
- [ ] T043 [US2] Convert `RebuildSearchIndexUseCase`/`SearchIndexRebuildHandler`, `CacheInvalidationHandler`, `CacheWarmupHandler` to `async def` in their respective files

### Tests for User Story 2

- [ ] T044 [P] [US2] Integration test: search index rebuild and cache invalidation/warmup complete — and are queryable/reflected — before a deliberately-slowed RAG task resolves, in `src/tests/integration/test_pipeline_barriers.py`
- [ ] T045 [P] [US2] Regression test: `CacheWarmupHandler` still runs strictly after `CacheInvalidationHandler` for the same `TextPipelineCompletedEvent` (assert call order, not just that both ran) in `src/tests/unit/test_in_memory_event_bus.py` — extends T007/T008
- [ ] T046 [P] [US2] Integration test: a run with zero RAG-eligible articles still fires `TextPipelineCompletedEvent` correctly (Edge Case) in `src/tests/integration/test_pipeline_barriers.py`

**Checkpoint**: User Stories 1 and 2 both work — visitors see freshly scraped content searchable without waiting on RAG.

---

## Phase 5: User Story 3 - Operators still get one accurate, complete run report (Priority: P3)

**Goal**: The operator completion notification and metrics reporting still fire once, only after RAG is also done, and accurately reflect every article's outcome at every stage.

**Independent Test**: In one run, induce a RAG failure for one article and an LLM rate-limit for another; confirm the completion notification reports both accurately and is sent only after RAG processing for the whole run finishes.

### Implementation for User Story 3

- [ ] T047 [US3] In `CollectionPipeline.run()`, await Barrier 2 after Barrier 1: `await asyncio.gather(*rag_tasks, return_exceptions=True)` (the RAG tasks collected in T034 across every article), then `await event_bus.publish(PipelineCompletedEvent(...))` — semantics unchanged from today, in `src/infrastructure/collection/collection_pipeline.py`
- [ ] T048 [US3] Convert `OtelMetricsHandler` to `async def` in `src/infrastructure/collection/handlers/`
- [ ] T049 [US3] Convert the Telegram notification handler (`build_notification_handler`/`PipelineCompletedMessageBuilder`) to `async def` in `src/infrastructure/shared/notifications/` and `src/infrastructure/collection/notifications/`
- [ ] T050 [US3] Convert `FailedTaskPersistenceHandler` to `async def`, using a per-call `AsyncSession`/`AsyncFailedTaskRepository` (T018) so concurrently-failing articles don't share mutable state, in `src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py`
- [ ] T051 [US3] Confirm `AsyncResilientLLMService`/`AsyncResilientEmbeddingService`'s `exhausted_providers` reporting (T024/T025) stays accurate when multiple concurrent article tasks trigger `RateLimitExhausted` for different providers within the same run — add any missing accounting in `src/infrastructure/intelligence/llm/resilient_llm_service.py`

### Tests for User Story 3

- [ ] T052 [P] [US3] Integration test: a run with one RAG failure and one LLM rate-limit event on different articles produces a completion notification accurately reporting both, sent only after RAG finishes, in `src/tests/integration/test_pipeline_completion_notification.py`
- [ ] T053 [P] [US3] Unit test: `PipelineStats.record()`/`RateLimitedProviderTracker.mark_exhausted()` remain correct under many concurrent callers (`asyncio.gather` of concurrent record/mark calls) in `src/tests/unit/test_pipeline_stats.py`
- [ ] T054 [P] [US3] Integration test: a permanently-failing article's `FailedTask` is recorded and it is absent from the rebuilt search index, while other articles are unaffected (Clarifications) in `src/tests/integration/test_pipeline_completion_notification.py`

**Checkpoint**: All three P1-P3 stories work together — the full two-barrier pipeline with accurate reporting, matching spec.md FR-001 through FR-008 and FR-013.

---

## Phase 6: User Story 4 - Multiple available models are used at once instead of queuing behind one (Priority: P4)

**Goal**: Concurrent analyze/translate/embedding calls spread across every registered model with spare capacity instead of serializing behind the single highest-priority one.

**Independent Test**: Register several low-`rpd` models for one capability; run a batch whose combined calls exceed any single model's daily quota; confirm multiple models are in concurrent use early in the run and total throughput exceeds what the single top-priority model alone could sustain.

### Implementation for User Story 4

- [ ] T055 [US4] Add non-blocking `has_capacity(estimated_tokens: int) -> bool` to `SlidingWindowStrategy` in `src/infrastructure/intelligence/llm/rate_limit/sliding_window_strategy.py` — reuses the existing `_lock`/`_rpm_wait`/`_tpm_wait`/`_daily_count` internals, adds no new state
- [ ] T056 [US4] Create `ProviderSelector` ABC + `PriorityFirstProviderSelector` default implementation in new `src/infrastructure/intelligence/llm/rate_limit/provider_selector.py`, mirroring `QueueSelector`'s shape (`src/infrastructure/collection/executor/queue_selector.py`) per contracts/provider-selector-port.md
- [ ] T057 [US4] Wire `ProviderSelector`-driven dispatch into `AsyncResilientLLMService.analyze/translate/generate` (T024): scan-select-reserve with no `await` inside the critical section (research.md item 7's invariant), falling back to the existing blocking-equivalent wait only when the whole pool is saturated (FR-011), in `src/infrastructure/intelligence/llm/resilient_llm_service.py`
- [ ] T058 [US4] Same wiring for `AsyncResilientEmbeddingService.embed/embed_batch` (T025), in the same file

### Tests for User Story 4

- [ ] T059 [P] [US4] Unit test: concurrent `analyze()` calls against a pool of mocked providers with small `rpd` values spread across multiple models rather than all serializing behind the top-priority one, in `src/tests/unit/test_provider_selector.py`
- [ ] T060 [P] [US4] Unit test: a model momentarily throttled within its per-minute window is skipped in favor of another model with spare capacity, but is not permanently excluded once its window clears (FR-010), in `src/tests/unit/test_provider_selector.py`
- [ ] T061 [P] [US4] Unit test: a stress test of many concurrent reservation attempts against a small pool never double-counts or drops a reservation (verifies the no-`await`-in-critical-section invariant holds under real `asyncio.gather` concurrency, not just by code inspection) in `src/tests/unit/test_provider_selector.py`
- [ ] T062 [P] [US4] Unit test: `exhausted_providers` reporting correctly lists every model that hit its daily cap during a run with concurrent dispatch across the pool (FR-012), in `src/tests/unit/test_async_resilient_llm_service.py`

**Checkpoint**: All four P1-P4 stories work together — the pipeline is concurrent end-to-end, including spreading LLM/embedding load across every available model.

---

## Phase 7: User Story 5 - The stage-handoff mechanism can later scale beyond one process without rewriting stages (Priority: P5)

**Goal**: Verify every pipeline stage depends only on the abstract `EventBus` Protocol, never a concrete implementation.

**Independent Test**: Substitute a stub `EventBus` implementation into the pipeline's wiring and confirm no stage's processing code needs to change.

### Implementation for User Story 5

- [ ] T063 [US5] Add a minimal stub `EventBus` Protocol implementation (in-memory call recorder, no real dispatch logic) in `src/tests/unit/fixtures/stub_event_bus.py`

### Tests for User Story 5

- [ ] T064 [P] [US5] Test substituting `StubEventBus` for `AsyncInMemoryEventBus` in `build_collection_pipeline()`'s wiring and confirming construction succeeds with no changes to any handler/use-case code, in `src/tests/unit/test_event_bus_swappability.py`
- [ ] T065 [P] [US5] Static check confirming no module outside `src/infrastructure/shared/events/` and `src/bootstrap.py` imports `AsyncInMemoryEventBus` directly (every other module imports only the `EventBus` Protocol type), in `src/tests/unit/test_event_bus_swappability.py`

**Checkpoint**: All five user stories complete and independently verified.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T066 [P] Update `scripts/generate_uml.py` to also recognize the new `_async_repo_impl.py` filename suffix for `infrastructure-persistence` layer classification, alongside the existing `_repo_impl.py` suffix (constitution Principle VIII)
- [ ] T067 Run `make uml-backend` and confirm the auto-generated pipeline diagram (`site/guide/architecture/uml`) renders `TextPipelineCompletedEvent` and `PipelineCompletedEvent` as two distinct branches with their correct handler sets
- [ ] T068 Run `specs/024-async-pipeline-refactor/quickstart.md` end-to-end against a local `docker compose` stack and confirm all manual scenarios and automated suites pass
- [ ] T069 [P] Update CLAUDE.md's "Scraper Pipeline Flow" numbered list to describe the two-barrier completion model (Discover → Pre-dedup → Fetch → Publish → Process/Analyze/Translate (concurrent, Barrier 1) → RAG (concurrent, Barrier 2) → Notify)
- [ ] T070 Explicitly verify (grep + manual read) that `build_weekly_pipeline()`, `build_metrics_refresh_pipeline()`, `build_dedup_reconciliation_pipeline()`, `build_rag_backfill_pipeline()`, and `build_translation_pipeline()` in `src/bootstrap.py` are byte-for-byte unchanged from their pre-feature state except for import-line additions, if any — the final confirmation that this feature's blast radius held to its intended scope
- [ ] T071 [P] Full audit of the remaining repositories not covered by T010-T018 (`ArticleDedupRepository`, `ArticleMetricsRepository`, `ScraperSettingRepository`, `SearchTermRepository`, `RagBackfillRepository`, `WeeklyReportTranslationRepository`) confirming none of them are used inside the now-concurrent per-article path (contracts/async-repository-ports.md's deferred audit) — add any missed async adapter if the audit finds one

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks every user story** — none of US1-US5's tests can pass without the async DB session, EventBus, repositories, providers, and services this phase builds.
- **User Story 1 (Phase 3)**: Depends on Foundational only. This is the MVP — the concurrency mechanism itself.
- **User Story 2 (Phase 4)**: Depends on Foundational **and** User Story 1 (the per-article `asyncio.Task`/RAG-detached-task machinery T032/T034 that Barrier 1 gathers over).
- **User Story 3 (Phase 5)**: Depends on Foundational, User Story 1, **and** User Story 2 (Barrier 2 is "the other half" of the split Barrier 1 introduced; the RAG-task collector Barrier 2 awaits is built in T034/US1).
- **User Story 4 (Phase 6)**: Depends on Foundational (specifically `AsyncResilientLLMService`/`AsyncResilientEmbeddingService`, T024/T025) — **independent of User Stories 1-3's barrier-splitting work**, could be implemented in parallel with Phases 3-5 by a different contributor once Phase 2 is done.
- **User Story 5 (Phase 7)**: Depends on Foundational only (the `EventBus` Protocol shape from T005/T006) — independent of every other user story, could be done any time after Phase 2.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- Within Phase 2: sub-sections 2c (T010-T018), 2d (T020-T022), and 2f (T028-T029, after 2d) touch disjoint files and can proceed in parallel once 2a/2b are done; 2e (T024-T026) depends on 2d's provider classes.
- Once Phase 2 is complete: **User Story 4 (Phase 6) and User Story 5 (Phase 7) can be worked entirely in parallel with User Stories 1→2→3 (Phases 3-5)**, since neither touches the barrier/orchestration machinery those three build sequentially on each other.
- All `[P]`-marked test tasks within any phase can run in parallel (distinct test files).

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (User Story 1).
2. **STOP and VALIDATE**: run `src/tests/integration/test_collection_pipeline_concurrency.py`, confirm real concurrent article processing and RAG decoupling work end-to-end. This alone delivers spec.md's SC-001.

### Incremental Delivery

1. Setup + Foundational → async infrastructure ready, nothing user-visible yet.
2. + User Story 1 → concurrent downstream processing, RAG decoupled (MVP, SC-001).
3. + User Story 2 → search/cache freshness no longer waits on RAG (SC-002).
4. + User Story 3 → completion reporting proven accurate under concurrency (SC-003) — the point at which this feature is safe to consider done for correctness, even before US4/US5.
5. + User Story 4 (can be built in parallel with 2-4 once Foundational is done) → model-pool throughput (SC-004).
6. + User Story 5 (can also be built in parallel) → verified swappability (SC-006).

### Notes

- `[P]` tasks touch different files with no unfinished dependency between them.
- `[Story]` labels map each task to its spec.md user story for traceability.
- Commit after each task or logical group (per this repo's commit-message convention — `<emoji> [FEAT|FIX|...] <message>`).
- The recurring "new sibling, don't touch the shared original" pattern (see the note at the top of this file) is the single most important thing to keep straight while working through Phase 2 — every task that names an existing shared file says explicitly whether it edits that file's existing code or only adds new code beside it.
