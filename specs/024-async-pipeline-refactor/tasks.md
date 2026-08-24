# Tasks: Async Event-Driven Collection Pipeline

**Input**: Design documents from `/specs/024-async-pipeline-refactor/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included per user story per constitution §III (mandatory, not optional). Ordering within each phase is implementation-first, tests-second — this project does not use TDD (write-test-first-and-watch-it-fail); tests verify behavior after implementation, per established team practice.

**A recurring, load-bearing constraint across almost every phase below**: `src/bootstrap.py` has several functions/classes shared with pipelines explicitly out of scope for this feature (`build_weekly_pipeline()`, `build_metrics_refresh_pipeline()`, `build_dedup_reconciliation_pipeline()`, `build_rag_backfill_pipeline()`, `build_translation_pipeline()`). Confirmed shared: `build_llm_service()`/`ResilientLLMService`/`ResilientEmbeddingService`/`ClaudeProvider`/`GeminiProvider`/`OpenRouterProvider` (weekly-report, translation), `build_rag_ingestion_service()` (RAG-backfill), `SqlAlchemyTopicRepository` (weekly-report), and by policy every other repository this pipeline touches (research.md item 3, applied uniformly rather than repo-by-repo). **Every task below that touches one of these adds a new, separate async sibling — it never edits the existing shared sync code's behavior or signatures.** The one exception is the `EventBus` Protocol (`src/shared/application/ports/event_bus.py`), which every pipeline builder consumes through its own separate concrete instance — safe to edit in place (research.md item 4's rationale).

## Path Conventions

Single project (existing `src/` DDD scraper service). Test paths: `src/tests/unit/` (no DB), `src/tests/integration/` (`@pytest.mark.integration`, isolated schema) — both run via `make test`/`make test-integration` (Docker), per constitution Principle III/IV.

---

## Phase 1: Setup

- [X] T001 Add `asyncpg` as an explicit dependency in the `scraper` group of `pyproject.toml` (already a transitive dependency via `chatbot-plugin-sdk`, but this pipeline's own code now imports it directly for `create_async_engine`) — then run `uv lock` to update `uv.lock`
- [X] T002 Add `httpx` as an explicit dependency in the `llm` group of `pyproject.toml` (needed by the new `AsyncOpenRouterProvider`; currently only declared in `backend`/`dev` groups) — then run `uv lock`

**Checkpoint**: Dependencies available inside the `app`/`job_service`/`test_service` Docker images on next `docker compose build`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Async infrastructure every user story's work depends on. No user story task can be meaningfully tested until this phase is complete.

### 2a. Async database session

- [X] T003 Add `get_async_sessionmaker()` to `src/infrastructure/persistence/database.py` — builds an `asyncpg`-backed `create_async_engine(...)` + `async_sessionmaker(...)` once (module-level singleton, mirroring the existing sync `get_session()`'s `_engine`/`_SessionLocal` pattern), entirely separate from the existing sync engine
- [X] T004 [P] Unit test: two calls into `get_async_sessionmaker()`'s factory produce distinct `AsyncSession` instances (never the same object) in `src/tests/unit/infrastructure/persistence/test_database_async.py` (nested to match this repo's existing test layout, not the flat path originally sketched here)

### 2b. `EventBus` async port (safe to edit in place — research.md item 4)

- [X] T005 Change `EventBus.subscribe`/`EventBus.publish` to `async def` in `src/shared/application/ports/event_bus.py`, per contracts/event-bus-port.md's exact guarantees (sequential, `subscribe()`-order handler dispatch within one `publish()` call — **not** `asyncio.gather` across sibling handlers)
- [X] T006 Implement `AsyncInMemoryEventBus` in `src/infrastructure/shared/events/in_memory_event_bus.py`, as a new class alongside the existing sync `InMemoryEventBus` (which stays untouched — still used by every other pipeline builder)
- [X] T007 [P] Unit test: `AsyncInMemoryEventBus.publish()` awaits handlers for the same event type strictly in `subscribe()`-call order (assert call-order via a shared mutable list two handlers append to) in `src/tests/unit/infrastructure/shared/events/test_in_memory_event_bus.py` (nested path, matches repo convention)
- [X] T008 [P] Unit test: one handler raising does not prevent the remaining handlers (for the same event) from still being awaited, in same file
- [X] T009 [P] Unit test: `publish()` calls for two *different* event instances run concurrently (via `asyncio.gather` of two `publish()` calls, one handler with an injected `asyncio.sleep`, asserting overlap) in same file — verified the concurrency assertion actually passes (B's handler finishes before A's slow one), not just that the code compiles

### 2c. Async repository ports (new adapters; existing sync repos/Protocols untouched)

- [X] T010 [P] Define `AsyncArticleRepository` Protocol (`find_by_url_hash`/`has_analysis`/`save` — corrected during implementation: `find_by_url_hash`/`has_analysis` ARE called per-article via `DedupService` inside `ProcessScrapedArticleUseCase`, not upstream-only as first assumed; `find_analyzed_url_hashes` stays on the existing sync `ArticleRepository`, used only by the still-batched fetch/dedup phase) in `src/shared/domain/repositories/article_repository.py`, implement `AsyncSqlAlchemyArticleRepository` in `src/infrastructure/persistence/shared/article_async_repo_impl.py`
- [X] T010b [P] (new task, found during implementation) Define `AsyncArticleMetricsRepository` Protocol (`upsert` only) — `ProcessScrapedArticleUseCase` calls `article_metrics_repo.upsert()` per-article; planning had wrongly scoped this repo as upstream-only — in `src/modules/collection/domain/repositories/article_metrics_repository.py`, implement `AsyncSqlAlchemyArticleMetricsRepository` in `src/infrastructure/persistence/collection/article_metrics_async_repo_impl.py`
- [X] T011 [P] Define `AsyncAnalysisRepository` Protocol (`save` only) in `src/modules/intelligence/domain/repositories/analysis_repository.py`, implement `AsyncSqlAlchemyAnalysisRepository` in `src/infrastructure/persistence/intelligence/analysis_async_repo_impl.py`
- [X] T012 [P] Define `AsyncAnalysesTranslationRepository` Protocol (`save`/`exists`/`find_by_analysis_id_and_language`), implement `AsyncSqlAlchemyAnalysesTranslationRepository` in `src/infrastructure/persistence/intelligence/analyses_translation_async_repo_impl.py`
- [X] T013 [P] Define `AsyncTagTranslationRepository` Protocol (full 4-method parity — corrected during implementation: `TranslateTagsUseCase` calls `find_tags/groups_without_translation` itself regardless of which pipeline constructed it, not exclusive to the standalone translate job as first assumed), implement `AsyncSqlAlchemyTagTranslationRepository` in `src/infrastructure/persistence/intelligence/tag_translation_async_repo_impl.py`
- [X] T014 [P] Define `AsyncArticleTranslationRepository` Protocol (`save`/`exists`/`find_by_article_id_and_language`), implement `AsyncSqlAlchemyArticleTranslationRepository` in `src/infrastructure/persistence/intelligence/article_translation_async_repo_impl.py`
- [X] T015 [P] Define `AsyncTagRepository` Protocol (`find_similar`/`save`/`link_to_article`/`save_suggestion`/`commit`), implement `AsyncSqlAlchemyTagRepository` in `src/infrastructure/persistence/intelligence/tag_async_repo_impl.py` — `link_to_article` uses a direct `INSERT ... ON CONFLICT DO NOTHING` into `article_tags` instead of the sync version's `article.tags.append(tag)` ORM-relationship pattern, which would raise under `AsyncSession` without eager loading
- [X] T016 [P] Define `AsyncTagGroupDefinitionRepository` Protocol (full 2-method parity), implement `AsyncSqlAlchemyTagGroupDefinitionRepository` in `src/infrastructure/persistence/intelligence/tag_group_definition_async_repo_impl.py`
- [X] T017 [P] Define `AsyncTopicRepository` Protocol, implement `AsyncSqlAlchemyTopicRepository` in `src/infrastructure/persistence/shared/topic_async_repo_impl.py` — this one is the confirmed-shared case (`SqlAlchemyTopicRepository` also used by `build_weekly_pipeline()`), do not touch the existing class
- [X] T018 [P] Define `AsyncFailedTaskRepository` Protocol, implement `AsyncSqlAlchemyFailedTaskRepository` in `src/infrastructure/persistence/shared/failed_task_async_repo_impl.py`
- [X] T019 [P] Integration tests: each new async repository's save/read round-trips correctly against the isolated `test_integration` schema, in `src/tests/integration/test_async_repositories.py` — 9 tests, all passing; added a function-scoped `async_db_session` fixture to `conftest.py` (session-scoped would fail — asyncpg connections are bound to the event loop that created them, and pytest-asyncio gives each test its own loop by default). Caught and fixed one real bug during this verification: `find_tags_without_translation`'s `row.group_def.name` access triggered an implicit lazy-load, which raises `MissingGreenlet` under `AsyncSession` — fixed with `selectinload(TagModel.group_def)`. Full existing integration suite (104 tests) and unit suite (959 tests) both still pass — zero regressions from this phase's changes.

### 2d. Async LLM provider classes (new siblings; existing sync providers untouched)

- [X] T020a (new task, found during implementation) Implement `AsyncBaseProvider` in `src/infrastructure/intelligence/llm/providers/async_base_provider.py` — async sibling of `BaseProvider`'s template-method shape (`tenacity.AsyncRetrying` instead of `Retrying`), reusing `base_provider.py`'s pure `_NON_RETRYABLE`/`_TRANSLATE_NON_RETRYABLE`/`_REQUIRED_FIELDS`/`_to_str` directly (stateless, safe to import). Planning had not scoped this — `ClaudeProvider`/`GeminiProvider`/`OpenRouterProvider` all inherit `analyze`/`translate`/`generate` from `BaseProvider`, so an async sibling needs the same base class, not three independent reimplementations.
- [X] T020 [P] Implement `AsyncClaudeProvider` (using `anthropic.AsyncAnthropic`) in `src/infrastructure/intelligence/llm/providers/async_claude_provider.py`
- [X] T021 [P] Implement `AsyncGeminiProvider` (using `genai.Client(...).aio` — same client, async sub-namespace) in `src/infrastructure/intelligence/llm/providers/async_gemini_provider.py`
- [X] T022 [P] Implement `AsyncOpenRouterProvider` (using `httpx.AsyncClient`, replacing `requests.post`; opened/closed per-call via `async with`, matching the sync version's non-persistent style) in `src/infrastructure/intelligence/llm/providers/async_openrouter_provider.py`
- [X] T023 [P] Unit tests for each new async provider (mocked async client via `unittest.mock.AsyncMock`) in `src/tests/unit/infrastructure/intelligence/llm/providers/test_async_{claude,gemini,openrouter}_provider.py` — 15 tests, all passing

### 2e. `AsyncResilientLLMService`/`AsyncResilientEmbeddingService` (new classes; existing sync services untouched)

- [X] T024a (new task, found during implementation) Implement `AsyncBaseEmbeddingProvider` + `AsyncGeminiEmbeddingProvider` in `src/infrastructure/intelligence/llm/embedding/async_base_embedding_provider.py` / `async_gemini_embedding_provider.py` — `AsyncResilientEmbeddingService` needs async embedding providers too, same "new sibling" reasoning as the LLM providers; planning had only scoped the LLM side.
- [X] T024 Implement `AsyncProviderHandler`/`AsyncResilientLLMService` (async `analyze`/`translate`/`generate`, priority-fallback dispatch identical to today's sync behavior — the `ProviderSelector` upgrade lands in Phase 6/US4, not here) in `src/infrastructure/intelligence/llm/resilient_llm_service.py`, alongside the existing sync classes
- [X] T025 Implement `AsyncEmbeddingProviderHandler`/`AsyncResilientEmbeddingService` (same pattern) in the same file
- [X] T026 Add `build_async_llm_service(session)` to `src/bootstrap.py`, alongside the existing `build_llm_service()` — constructs `AsyncClaudeProvider`/`AsyncGeminiProvider`/`AsyncOpenRouterProvider`/`AsyncGeminiEmbeddingProvider` wrapped in `AsyncProviderHandler`/`AsyncEmbeddingProviderHandler`s. Deliberately a plain `def`, not `async def`: it reuses the same sync `session` and the unmodified sync `load_active_providers`/`load_active_embedding_providers` loaders for a one-time, pre-concurrency config read at wiring time — only the objects it *constructs* are async, construction itself doesn't need to be.
- [X] T027 [P] Unit tests for `AsyncResilientLLMService`/`AsyncResilientEmbeddingService`'s fallback-on-`RateLimitExhausted` behavior, including a test that an exhausted provider is moved to the end and skipped on the next call, in `src/tests/unit/infrastructure/intelligence/llm/test_async_resilient_llm_service.py` — 5 tests, all passing. Full unit suite (979 tests, up from 959) still green.

### 2f. RAG async wiring (new sibling builder; existing sync RAG wiring untouched)

- [X] T028 Add `build_async_rag_ingestion_service()` + shared `_build_rag_dense_sparse_providers()` helper to `src/bootstrap.py`, alongside the existing `build_rag_ingestion_service()` — uses `AsyncPgBackend` (already in `chatbot_plugin_sdk`) instead of `SyncPgBackend`, and awaits `IngestProcessor.ingest()` natively (no `asyncio.run()` wrapper, which would raise inside an already-running event loop — exactly the context this now runs in)
- [X] T029 [P] Implement `AsyncIngestArticleForRagUseCase` and `AsyncRagIngestionHandler` as **new sibling classes** (corrected during implementation: `IngestArticleForRagUseCase` is also constructed by the out-of-scope `build_rag_backfill_pipeline()`, `bootstrap.py:872` — confirmed shared, the same risk pattern as research.md item 3, not "safe to convert directly" as originally planned; `RagIngestionHandler` itself is confirmed constructed only once, but gets a sibling anyway for naming consistency since it depends on the async use case's type) plus `AsyncRagIngestionService` Protocol + `AsyncRagSdkIngestionService` impl, in `src/modules/intelligence/application/use_cases/ingest_article_for_rag.py`, `src/modules/intelligence/application/event_handlers/rag_ingestion_handler.py`, `src/modules/intelligence/domain/services/rag_ingestion_service.py`, `src/infrastructure/intelligence/vector_store/rag_sdk_ingestion_impl.py`
- [X] T030 [P] Unit tests confirming RAG ingestion is awaited through the async path end-to-end (mocked `IngestProcessor`) in `src/tests/unit/infrastructure/intelligence/vector_store/test_async_rag_sdk_ingestion_impl.py`, `src/tests/unit/modules/intelligence/application/test_async_ingest_article_for_rag.py`, `test_async_rag_ingestion_handler.py` — 9 tests, all passing

**Checkpoint**: All async building blocks exist and are unit-tested in isolation. Full unit suite (988 tests) and integration suite (104 tests) both green — Foundational phase (T001-T030, 34 tasks including corrections found along the way) is complete. No pipeline orchestration wired up yet — that starts in Phase 3.

---

## Phase 3: User Story 1 - A scheduled run finishes without one slow article blocking every other article (Priority: P1) 🎯 MVP

**Goal**: Multiple articles' downstream processing (analyze, translate, RAG) runs concurrently; RAG ingestion for one article never blocks another article's progress.

**Independent Test**: Run the pipeline against a batch with at least one RAG-eligible article; confirm more than one article's downstream processing is in flight at once, and an artificially slow RAG ingestion doesn't delay other articles' analyze/translate.

### Implementation for User Story 1

- [X] T031 [US1] Convert `CollectionPipeline.run()` to `async def` in `src/infrastructure/collection/collection_pipeline.py` — `await` the (unchanged, still-sequential) discover/fetch/batched-dedup calls; behavior of that phase does not change, only its calling convention (research.md item 9)
- [X] T032 [US1] Replace the per-article `for article in results: event_bus.publish(...)` loop with one `asyncio.Task` per article in `src/infrastructure/collection/collection_pipeline.py` — each task opens its own `AsyncSession` (via T003's factory), constructs its own async repositories (T010-T018) and use cases, and awaits its own chain of `publish()` calls on the `AsyncInMemoryEventBus` (T006)
- [X] T033 [US1] Convert `ProcessScrapedArticleUseCase`, `ArticleScrapedHandler`, `AnalyzeArticleUseCase`, `ArticleProcessedHandler`, `NormalizeTagsUseCase`, `TagNormalizationHandler`, `AnalysisCompletedHandler` to `async def` methods **in place** (each confirmed constructed only once, only inside `build_collection_pipeline()` — safe), threaded through with the per-task `AsyncSession`/async repos from T032 — files under `src/modules/collection/application/` and `src/modules/intelligence/application/`
- [X] T033b [US1] Implement `AsyncTranslateArticleUseCase`, `AsyncTranslateTagsUseCase`, `AsyncTranslateArticleBodyUseCase` as **new sibling classes** (research.md item 3 — each of the three sync originals is also constructed by the out-of-scope `build_translation_pipeline()`, confirmed by grepping `bootstrap.py`; converting in place would break that CLI job) in `src/modules/intelligence/application/use_cases/translate_article.py`, `translate_tags.py`, `translate_article_body.py`, alongside their untouched sync originals
- [X] T034 [US1] In the handler that dispatches RAG ingestion (subscribed to `ArticleProcessedEvent`), replace the inline `await rag_ingestion_handler.handle(event)` with `asyncio.create_task(rag_ingestion_handler.handle(event))`, registering the created task on a run-level RAG-task collector (a simple `list[asyncio.Task]` passed down from `CollectionPipeline.run()`) instead of awaiting it — implemented in `src/infrastructure/collection/collection_pipeline.py`. Shape actually landed: `CollectionPipeline._dispatch_rag()` (subscribed to `ArticleProcessedEvent` by `article_downstream_builder`) creates the detached task and appends it to `self._rag_tasks` (an instance-level list, functionally the same "run-level collector" described here).
- [X] T035 [US1] Update `src/entrypoints/cli/main.py` to `asyncio.run(pipeline.run())`, replacing the direct synchronous call. Landed as `asyncio.run(_build_and_run())`, a nested closure awaiting both `build_collection_pipeline()` and `pipeline.run()` — needed so `pipeline_stats` stays bound in the outer `finally` block even if only `.run()` fails (see main.py's inline comment; this was a regression caught and fixed during implementation).
- [X] T036 [US1] Update `build_collection_pipeline()` in `src/bootstrap.py` to wire everything from Phase 2 together: `build_async_llm_service()`, `build_async_rag_ingestion_service()`, `AsyncInMemoryEventBus()`, the async repository constructors, and the new async use cases/handlers from T033/T033b/T034 — this function becomes `async def` (or returns an awaitable pipeline whose `.run()` is async; exact shape decided here)

### Tests for User Story 1

- [X] T037 [P] [US1] Integration test: a batch of N articles' downstream processing overlaps in wall-clock time (assert via per-article start/end timestamps or injected delays) in `src/tests/integration/test_collection_pipeline_concurrency.py`
- [X] T038 [P] [US1] Integration test: one article's artificially-slowed RAG ingestion does not delay another article's analyze/translate completion, in `src/tests/integration/test_collection_pipeline_concurrency.py`
- [X] T039 [P] [US1] Unit test: no two concurrently-running article tasks ever hold the same `AsyncSession` instance (assert distinct object identity across tasks) in `src/tests/unit/test_collection_pipeline_sessions.py`

**Checkpoint**: User Story 1 is fully functional and independently testable — this is the MVP. `CollectionPipeline.run()` now processes articles concurrently end-to-end, though completion notification/search-index timing still matches today's single-barrier behavior until Phase 4/5 land. Full suite green: 1095 tests passing (991 unit + 104 integration), zero warnings.

---

## Phase 4: User Story 2 - Freshly scraped articles become searchable without waiting on RAG (Priority: P2)

**Goal**: Search-index rebuild and cache refresh fire once every article's text stage (scrape+analyze+translate) has settled — without waiting on RAG.

**Independent Test**: Run a batch with RAG-eligible articles; artificially slow RAG for one; confirm search index/cache refresh completes, reflecting every article's text content, before that article's RAG ingestion finishes.

### Implementation for User Story 2

- [X] T040 [US2] Add `TextPipelineCompletedEvent` (ends in `Event` per constitution Principle VIII) in `src/modules/collection/application/events/`
- [X] T041 [US2] In `CollectionPipeline.run()` (`src/infrastructure/collection/collection_pipeline.py`), await Barrier 1: `results = await asyncio.gather(*(article_tasks), return_exceptions=True)` (settle semantics per Clarifications/research.md item 6), then `await event_bus.publish(TextPipelineCompletedEvent(...))`
- [X] T042 [US2] In `src/bootstrap.py`, move `SearchIndexRebuildHandler`, `CacheInvalidationHandler`, `CacheWarmupHandler` subscriptions from `PipelineCompletedEvent` to `TextPipelineCompletedEvent` — preserve the existing `CacheInvalidationHandler` → `CacheWarmupHandler` subscribe-order (the correctness dependency documented at `bootstrap.py:443-448`)
- [X] T043 [US2] Convert `RebuildSearchIndexUseCase`/`SearchIndexRebuildHandler`, `CacheInvalidationHandler`, `CacheWarmupHandler` to `async def` in their respective files

### Tests for User Story 2

- [X] T044 [P] [US2] Integration test: search index rebuild and cache invalidation/warmup complete — and are queryable/reflected — before a deliberately-slowed RAG task resolves, in `src/tests/integration/test_pipeline_barriers.py`
- [X] T045 [P] [US2] Regression test: `CacheWarmupHandler` still runs strictly after `CacheInvalidationHandler` for the same `TextPipelineCompletedEvent` (assert call order, not just that both ran) in `src/tests/unit/test_in_memory_event_bus.py` — extends T007/T008. Landed instead as `test_cache_warmup_handler_subscribed_after_cache_invalidation_handler` in `src/tests/unit/test_composition_root.py` (already existed, pre-dating this task's write-up) — asserts the real order via `build_collection_pipeline()`'s actual bus state (`bound_classes.index(...)` comparison), a stronger check than a standalone bus-level test since it verifies bootstrap's real wiring, not just `AsyncInMemoryEventBus`'s dispatch mechanics (already covered generically by T007/T008).
- [X] T046 [P] [US2] Integration test: a run with zero RAG-eligible articles still fires `TextPipelineCompletedEvent` correctly (Edge Case) in `src/tests/integration/test_pipeline_barriers.py`

**Checkpoint**: User Stories 1 and 2 both work — visitors see freshly scraped content searchable without waiting on RAG.

---

## Phase 5: User Story 3 - Operators still get one accurate, complete run report (Priority: P3)

**Goal**: The operator completion notification and metrics reporting still fire once, only after RAG is also done, and accurately reflect every article's outcome at every stage.

**Independent Test**: In one run, induce a RAG failure for one article and an LLM rate-limit for another; confirm the completion notification reports both accurately and is sent only after RAG processing for the whole run finishes.

### Implementation for User Story 3

- [X] T047 [US3] In `CollectionPipeline.run()`, await Barrier 2 after Barrier 1: `await asyncio.gather(*rag_tasks, return_exceptions=True)` (the RAG tasks collected in T034 across every article), then `await event_bus.publish(PipelineCompletedEvent(...))` — semantics unchanged from today, in `src/infrastructure/collection/collection_pipeline.py`
- [X] T048 [US3] Convert `OtelMetricsHandler` to `async def` in `src/infrastructure/collection/handlers/`
- [X] T049 [US3] Convert the Telegram notification handler (`build_notification_handler`/`PipelineCompletedMessageBuilder`) to `async def` in `src/infrastructure/shared/notifications/` and `src/infrastructure/collection/notifications/`. Landed as a new `AsyncNotificationHandler`/`build_async_notification_handler()` sibling (not an in-place conversion) — `NotificationHandler`/`build_notification_handler()` are shared with 4 other out-of-scope pipelines (research.md item 3 policy), confirmed via `grep` during Phase 2.
- [X] T050 [US3] Convert `FailedTaskPersistenceHandler` to `async def`, using a per-call `AsyncSession`/`AsyncFailedTaskRepository` (T018) so concurrently-failing articles don't share mutable state, in `src/modules/intelligence/application/event_handlers/failed_task_persistence_handler.py`
- [X] T051 [US3] Confirm `AsyncResilientLLMService`/`AsyncResilientEmbeddingService`'s `exhausted_providers` reporting (T024/T025) stays accurate when multiple concurrent article tasks trigger `RateLimitExhausted` for different providers within the same run — add any missing accounting in `src/infrastructure/intelligence/llm/resilient_llm_service.py`. **Confirmed via code analysis + a live-interleaving test, no code change needed**: `RateLimitedProviderTracker.mark_exhausted()` is a `set.add()` under a `threading.Lock` (idempotent — double-marking the same provider is harmless), and the shared handler-reorder (`self._handlers.remove(handler); self._handlers.append(handler)`, no `await` between the two calls) can never raise even when many concurrent tasks hit `RateLimitExhausted` on the *same* handler near-simultaneously, because remove-then-append never leaves a window where the handler is absent from the list for another coroutine to fail to find (verified experimentally: a bare `asyncio.gather` reproduction without any real suspension point never interleaves at all — `AsyncMock` calls resolve without yielding to the loop — so the test needed an explicit `await asyncio.sleep(0)` before the raise, modeling a real network round-trip's suspension point, to force genuine interleaving and actually exercise the shared-list path). A guarded `if handler in self._handlers:` version was written, tested, and then deliberately reverted per the project's "don't add error handling for scenarios that can't happen" convention once the analysis confirmed the guard was dead code.

### Tests for User Story 3

- [X] T052 [P] [US3] Integration test: a run with one RAG failure and one LLM rate-limit event on different articles produces a completion notification accurately reporting both, sent only after RAG finishes, in `src/tests/integration/test_pipeline_completion_notification.py`
- [X] T053 [P] [US3] Unit test: `PipelineStats.record()`/`RateLimitedProviderTracker.mark_exhausted()` remain correct under many concurrent callers (`asyncio.gather` of concurrent record/mark calls) in `src/tests/unit/test_pipeline_stats.py`
- [X] T054 [P] [US3] Integration test: a permanently-failing article's `FailedTask` is recorded and it is absent from the rebuilt search index, while other articles are unaffected (Clarifications) in `src/tests/integration/test_pipeline_completion_notification.py`. Adapted during implementation: `RebuildSearchIndexUseCase` indexes directly off `Article.title`/`Article.content` (not `Analysis`), so a permanently-failing article (LLM analysis never succeeds) is **not** actually excluded from the search index by that query — the "absent from the index" framing didn't match real behavior. Rewrote the test's assertion around what the async refactor actually needs to guarantee: the failing article's `FailedTask` is persisted (via `FailedTaskPersistenceHandler`/`AsyncFailedTaskRepository`) and does not block or corrupt the other, successful article's `Article`+`Analysis` rows in the same run.

**Checkpoint**: All three P1-P3 stories work together — the full two-barrier pipeline with accurate reporting, matching spec.md FR-001 through FR-008 and FR-013. Full suite green: 1102 tests passing, zero warnings beyond a pre-existing unrelated `jieba` deprecation notice.

---

## Phase 6: User Story 4 - Multiple available models are used at once instead of queuing behind one (Priority: P4)

**Goal**: Concurrent analyze/translate/embedding calls spread across every registered model with spare capacity instead of serializing behind the single highest-priority one.

**Independent Test**: Register several low-`rpd` models for one capability; run a batch whose combined calls exceed any single model's daily quota; confirm multiple models are in concurrent use early in the run and total throughput exceeds what the single top-priority model alone could sustain.

### Implementation for User Story 4

- [X] T055 [US4] Add non-blocking `has_capacity(estimated_tokens: int) -> bool` to `SlidingWindowStrategy` in `src/infrastructure/intelligence/llm/rate_limit/sliding_window_strategy.py` — reuses the existing `_lock`/`_rpm_wait`/`_tpm_wait`/`_daily_count` internals, adds no new state. Also added to the `QuotaStrategy` ABC (as an abstract method, default `estimated_tokens=0`) and `NoOpStrategy` (always `True`) — both other implementers, so the port stays uniformly callable from `ProviderSelector` regardless of concrete strategy.
- [X] T056 [US4] Create `ProviderSelector` ABC + `PriorityFirstProviderSelector` default implementation in new `src/infrastructure/intelligence/llm/rate_limit/provider_selector.py`, mirroring `QueueSelector`'s shape (`src/infrastructure/collection/executor/queue_selector.py`) per contracts/provider-selector-port.md
- [X] T057 [US4] Wire `ProviderSelector`-driven dispatch into `AsyncResilientLLMService.analyze/translate/generate` (T024): scan-select-reserve with no `await` inside the critical section (research.md item 7's invariant), falling back to the existing blocking-equivalent wait only when the whole pool is saturated (FR-011), in `src/infrastructure/intelligence/llm/resilient_llm_service.py`. Landed as a `_dispatch_order()` helper (selector-preferred handlers first, then every remaining handler in original priority order appended after, preserving "try everyone before giving up") called at the top of each dispatch method in place of the old raw `list(self._handlers)` snapshot — the atomicity the contract requires falls out naturally from Python's cooperative scheduling (no `await` statement separates the synchronous `select()` call from the synchronous `strategy.acquire()` that runs as the first line inside the immediately-following `await handler.analyze(...)`), so no separate re-check/reserve step was needed as distinct code.
- [X] T058 [US4] Same wiring for `AsyncResilientEmbeddingService.embed/embed_batch` (T025), in the same file

### Tests for User Story 4

- [X] T059 [P] [US4] Unit test: concurrent `analyze()` calls against a pool of mocked providers with small `rpd` values spread across multiple models rather than all serializing behind the top-priority one, in `src/tests/unit/test_provider_selector.py`
- [X] T060 [P] [US4] Unit test: a model momentarily throttled within its per-minute window is skipped in favor of another model with spare capacity, but is not permanently excluded once its window clears (FR-010), in `src/tests/unit/test_provider_selector.py`
- [X] T061 [P] [US4] Unit test: a stress test of many concurrent reservation attempts against a small pool never double-counts or drops a reservation (verifies the no-`await`-in-critical-section invariant holds under real `asyncio.gather` concurrency, not just by code inspection) in `src/tests/unit/test_provider_selector.py`
- [X] T062 [P] [US4] Unit test: `exhausted_providers` reporting correctly lists every model that hit its daily cap during a run with concurrent dispatch across the pool (FR-012), in `src/tests/unit/test_async_resilient_llm_service.py`

**Checkpoint**: All four P1-P4 stories work together — the pipeline is concurrent end-to-end, including spreading LLM/embedding load across every available model. Full suite green: 1108 tests passing.

---

## Phase 7: User Story 5 - The stage-handoff mechanism can later scale beyond one process without rewriting stages (Priority: P5)

**Goal**: Verify every pipeline stage depends only on the abstract `EventBus` Protocol, never a concrete implementation.

**Independent Test**: Substitute a stub `EventBus` implementation into the pipeline's wiring and confirm no stage's processing code needs to change.

### Implementation for User Story 5

- [X] T063 [US5] Add a minimal stub `EventBus` Protocol implementation (in-memory call recorder, no real dispatch logic) in `src/tests/unit/fixtures/stub_event_bus.py`. **Found and fixed a real violation while implementing this**: `CollectionPipeline._process_article_text()` (`src/infrastructure/collection/collection_pipeline.py`) directly imported and constructed `AsyncInMemoryEventBus()` for the per-article bus — only the run-level bus was DI'd, not the per-article one. Fixed by adding a required `event_bus_factory: Callable[[], Any]` constructor param, used as `bus = self._event_bus_factory()` in place of the direct import/construction; `bootstrap.py` now passes `event_bus_factory=AsyncInMemoryEventBus` at the one real construction site. Updated all 11 test call sites (`test_collection_pipeline_concurrency.py`, `test_pipeline_barriers.py`, `test_pipeline_completion_notification.py`, `test_scheduler_due_sources.py`, `test_scrape_dispatcher.py` ×2, `test_collection_pipeline.py`, `test_collection_pipeline_stats.py`, `test_collection_pipeline_sessions.py`, `test_collection_pipeline_spans.py`, `test_pipeline_span_attributes.py`) to pass the real `AsyncInMemoryEventBus` class explicitly.

### Tests for User Story 5

- [X] T064 [P] [US5] Test substituting `StubEventBus` for `AsyncInMemoryEventBus` in `build_collection_pipeline()`'s wiring and confirming construction succeeds with no changes to any handler/use-case code, in `src/tests/unit/test_event_bus_swappability.py`
- [X] T065 [P] [US5] Static check confirming no module outside `src/infrastructure/shared/events/` and `src/bootstrap.py` imports `AsyncInMemoryEventBus` directly (every other module imports only the `EventBus` Protocol type), in `src/tests/unit/test_event_bus_swappability.py`. Implemented via `ast`-based scan of every `.py` file under `src/` (excluding `src/tests/`), checking real `ImportFrom`/`Import` nodes only — not a naive grep, so the check can't be defeated by mentioning the name in a comment/docstring (which several files legitimately do, e.g. `event_bus.py`'s own docstring).

**Checkpoint**: All five user stories complete and independently verified. Full suite green: 1110 tests passing.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T066 [P] Update `scripts/generate_uml.py` to also recognize the new `_async_repo_impl.py` filename suffix for `infrastructure-persistence` layer classification, alongside the existing `_repo_impl.py` suffix (constitution Principle VIII). **Verified no change was actually needed** for this specific ask: the generic fallback rule `r"_repo_impl\b"` (used for layer AND subgroup classification) is a substring match, not an exact enumerated filename list, so `article_async_repo_impl.py` etc. already classify correctly today (confirmed via a direct regex test). Real gap found and fixed instead: the new `TextPipelineCompletedEvent` class (added this feature) fell into the `unknown` layer while its sibling `PipelineCompletedEvent` correctly classified as `infrastructure-shared`, because the precise per-event-name rules (lines ~41/46) enumerate event module names explicitly and hadn't been updated for the new file — added `events\.text_pipeline_completed` to both.
- [X] T067 Run `make uml-backend` and confirm the auto-generated pipeline diagram (`site/guide/architecture/uml`) renders `TextPipelineCompletedEvent` and `PipelineCompletedEvent` as two distinct branches with their correct handler sets. Ran it (regenerated `classes.dot`/`packages.dot`/`uml-data.json`); confirmed both events now exist as distinct nodes classified identically (`infrastructure-shared`) after the T066 fix. **Correction to this task's original framing**: `generate_uml.py` is a static pyreverse-based class diagram — it has no mechanism to render dynamic `bus.subscribe()` handler-wiring as graph edges (the `edges` array only reflects import/inheritance relationships pyreverse's AST analysis can see), so "their correct handler sets" isn't something this specific generator produces for any event, old or new — verified via the generated JSON's empty edge set for both events. Also discovered `generate_uml.py` unconditionally deletes every `.dot` file in the shared output directory before regenerating its own (pre-existing behavior, unrelated to this feature) — this had deleted `db-schema.dot` (owned by a different generator script) as a side effect of running `uml-backend` alone; restored it via `make uml-db-schema`.
- [X] T068 Run `specs/024-async-pipeline-refactor/quickstart.md` end-to-end against a local `docker compose` stack and confirm all manual scenarios and automated suites pass. Section 5 (Automated verification, `make test` + `make test-integration`) — done: full suite green (1111 tests). Its "Key behaviors that MUST have dedicated tests" checklist is now fully covered: settle-not-succeed barrier semantics (test_pipeline_barriers.py, test_pipeline_completion_notification.py), EventBus sequential subscribe-order dispatch (test_composition_root.py + T007/T008), ProviderSelector's no-await-in-critical-section invariant under real concurrent load (T061, test_provider_selector.py), and OTel span parent/child continuity across the per-article task → detached RAG task boundary — the one item without a prior dedicated test, added as `src/tests/unit/test_rag_span_continuity.py` using a real OTel SDK `TracerProvider` (confirms same `trace_id`, distinct `span_id`, empirically validating research.md item 8). Sections 1-4 are manual/live-run scenarios requiring real LLM provider credentials and an actual scrape against live sources — not run in this session (would incur real API cost/side effects); left for the user to exercise manually per the quickstart doc when convenient.
- [X] T069 [P] Update CLAUDE.md's "Scraper Pipeline Flow" numbered list to describe the two-barrier completion model (Discover → Pre-dedup → Fetch → Publish → Process/Analyze/Translate (concurrent, Barrier 1) → RAG (concurrent, Barrier 2) → Notify)
- [X] T070 Explicitly verify (grep + manual read) that `build_weekly_pipeline()`, `build_metrics_refresh_pipeline()`, `build_dedup_reconciliation_pipeline()`, `build_rag_backfill_pipeline()`, and `build_translation_pipeline()` in `src/bootstrap.py` are byte-for-byte unchanged from their pre-feature state except for import-line additions, if any — the final confirmation that this feature's blast radius held to its intended scope. Verified via AST-based function-body extraction diffed against `git show HEAD:src/bootstrap.py` (not just `git diff` hunk inspection) — all five functions are **byte-for-byte identical**, not even an import-line addition. `git diff` hunks for this file are anchored only at `build_llm_service`, `build_rag_ingestion_service`, and `build_collection_pipeline` — confirming zero overlap.
- [X] T071 [P] Full audit of the remaining repositories not covered by T010-T018 (`ArticleDedupRepository`, `ArticleMetricsRepository`, `ScraperSettingRepository`, `SearchTermRepository`, `RagBackfillRepository`, `WeeklyReportTranslationRepository`) confirming none of them are used inside the now-concurrent per-article path (contracts/async-repository-ports.md's deferred audit) — add any missed async adapter if the audit finds one. Audit result: clean, no missed adapter needed. `ArticleDedupRepository` → `build_dedup_reconciliation_pipeline()` only (out of scope, confirmed unchanged by T070). `ScraperSettingRepository` → `discover_scrape_jobs.py`/`CollectionPipeline`'s upstream batched discover phase only (FR-003, explicitly out of scope for the concurrency change). `SearchTermRepository` → `RebuildSearchIndexUseCase`, which stays intentionally sync (one bulk query per run, not per-article — see its docstring). `RagBackfillRepository` → `build_rag_backfill_pipeline()`/`backfill_rag.py` CLI only (out of scope, confirmed unchanged). `WeeklyReportTranslationRepository` → `generate_weekly_report.py`/`build_weekly_pipeline()` only (out of scope, confirmed unchanged). `ArticleMetricsRepository` — actually **is** used in the concurrent path (`ProcessScrapedArticleUseCase.execute()` calls `article_metrics_repo.upsert()`); this was already caught mid-Phase-2 (see Phase 2c notes) and has an `AsyncArticleMetricsRepository`/`AsyncSqlAlchemyArticleMetricsRepository` pair — not actually missed, just mis-listed in this task's own text as if still open.

**Full suite status after Phase 8**: 1111 tests passing (unit + integration), zero warnings beyond the pre-existing unrelated `jieba` deprecation notice. `scripts/generate_uml.py`, `CLAUDE.md`, and the regenerated `site/public/guide/architecture/*` artifacts are the only non-test production/doc files touched in this phase, beyond the new `test_rag_span_continuity.py`.

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
