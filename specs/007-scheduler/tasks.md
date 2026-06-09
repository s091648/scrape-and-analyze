# Tasks: Scheduler & Pipeline Assembly

**Input**: Design documents from `/specs/007-scheduler/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This is a brownfield feature — all tasks are verification tests that confirm existing behaviour matches the spec.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/` at repository root
- **Unit tests**: `src/tests/unit/`
- **Integration tests**: `src/tests/integration/`
- Test execution: `make test` (unit, Docker), `make test-integration` (integration, Docker)

---

## Phase 1: Setup (Shared Test Infrastructure)

**Purpose**: Create shared test fixtures and helpers for scheduler verification tests.

- [ ] T001 Create test fixtures for scheduler entry point mocking (mock time.sleep, validate_config, configure_logging, build_collection_pipeline, push_metrics, shutdown_tracing, signal.signal) in `src/tests/unit/entrypoints/cli/conftest.py`
- [ ] T002 [P] Create integration test conftest for due-source selection tests (ScraperSetting factory, schema setup, per-test rollback) in `src/tests/integration/test_scheduler_due_sources_conftest.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish baseline test coverage for the existing `check_timeout()` and `validate_config()` functions before expanding to user story tests.

- [ ] T003 [P] Add test for `validate_config()` raising ValueError when DATABASE_URL is empty in `src/tests/unit/config/test_settings.py`
- [ ] T004 [P] Add test for `validate_config()` passing when DATABASE_URL is set in `src/tests/unit/config/test_settings.py`

**Checkpoint**: Basic config validation covered; ready for user story test phases

---

## Phase 3: User Story 1 - Scheduled Pipeline Run (Priority: P1) 🎯 MVP

**Goal**: Verify the run-once entry point lifecycle: config validation → jitter → run context → pipeline execution → teardown.

**Independent Test**: Run `make test` and verify all US1 scenarios pass: missing DATABASE_URL raises error, jitter sleep is applied or skipped based on RUN_IMMEDIATELY, pipeline runs and exits cleanly, finally block always executes.

### Verification Tests for User Story 1

- [ ] T005 [US1] Test that `main()` raises ValueError when DATABASE_URL is not set in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T006 [US1] Test that `main()` calls `time.sleep()` with a value in [0, 180] when RUN_IMMEDIATELY is not set in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T007 [US1] Test that `main()` does NOT call `time.sleep()` when RUN_IMMEDIATELY is set in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T008 [US1] Test that `main()` generates and binds a run_id and correlation_id to structlog context in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T009 [US1] Test that `main()` registers signal handlers for SIGTERM and SIGINT in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T010 [US1] Test that `main()` calls `build_collection_pipeline()` and then `pipeline.run()` in sequence in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T011 [US1] Test that `main()` calls `push_metrics()` and `shutdown_tracing()` in the finally block even when `pipeline.run()` raises an exception in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T012 [US1] Test that `main()` increments the SCRAPER_RUNS OTel counter at startup in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T013 [US1] Test that `main()` records wall-clock duration in SCRAPER_DURATION histogram in the finally block in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T014 [US1] Test that `main()` starts an OTel span named "scraper.run" with run.id and run.correlation_id attributes in `src/tests/unit/entrypoints/cli/test_main.py`

**Checkpoint**: US1 fully verified — entry point lifecycle matches spec

---

## Phase 4: User Story 2 - Pipeline Assembly & Event Wiring (Priority: P2)

**Goal**: Verify the composition root wires all repositories, event bus, LLM services, use cases, and event handler subscriptions correctly.

**Independent Test**: Run `make test` and verify `build_collection_pipeline()` returns a pipeline with the correct event bus subscriptions and that it raises ValueError when no LLM providers are active.

### Verification Tests for User Story 2

- [ ] T015 [P] [US2] Test that `build_collection_pipeline()` raises ValueError when no active LLM providers exist in `src/tests/unit/test_composition_root.py`
- [ ] T016 [P] [US2] Test that `build_collection_pipeline()` returns a CollectionPipeline with an InMemoryEventBus that has a subscription for ArticleScrapedEvent → ArticleScrapedHandler in `src/tests/unit/test_composition_root.py`
- [ ] T017 [P] [US2] Test that `build_collection_pipeline()` returns a CollectionPipeline with InMemoryEventBus subscriptions for ArticleProcessedEvent → ArticleProcessedHandler in `src/tests/unit/test_composition_root.py`
- [ ] T018 [P] [US2] Test that `build_collection_pipeline()` wires AnalysisCompletedEvent → TagNormalizationHandler in `src/tests/unit/test_composition_root.py`
- [ ] T019 [P] [US2] Test that `build_collection_pipeline()` wires TagNormalizationCompletedEvent → AnalysisCompletedHandler in `src/tests/unit/test_composition_root.py`
- [ ] T020 [P] [US2] Test that `build_collection_pipeline()` wires AnalysisFailedEvent, TagNormalizationFailedEvent, and TranslationFailedEvent → FailedTaskPersistenceHandler in `src/tests/unit/test_composition_root.py`
- [ ] T021 [P] [US2] Test that `build_collection_pipeline()` wires PipelineCompletedEvent → OtelMetricsHandler and notification handler in `src/tests/unit/test_composition_root.py`
- [ ] T022 [US2] Test that `build_collection_pipeline()` creates 10 repository instances all sharing the same session in `src/tests/unit/test_composition_root.py`
- [ ] T023 [US2] Test that `build_collection_pipeline()` creates a ScrapeExecutor with an on_discover_failed callback in `src/tests/unit/test_composition_root.py`

**Checkpoint**: US2 fully verified — composition root wiring matches spec

---

## Phase 5: User Story 3 - Due Source Selection (Priority: P2)

**Goal**: Verify that `get_active_due()` correctly selects active sources whose interval has elapsed (with 30-min tolerance) and that `mark_scraped()` updates last_scraped_at.

**Independent Test**: Run `make test-integration` and verify due-selection scenarios: never-scraped source included, elapsed-with-tolerance included, not-yet-elapsed excluded, inactive excluded.

### Verification Tests for User Story 3

- [ ] T024 [US3] Integration test: a source that has never been scraped is included in `get_active_due()` results in `src/tests/integration/test_scheduler_due_sources.py`
- [ ] T025 [US3] Integration test: an active source last scraped 5 hours ago with 4-hour frequency is included (elapsed > interval − tolerance) in `src/tests/integration/test_scheduler_due_sources.py`
- [ ] T026 [US3] Integration test: an active source last scraped 3.5 hours ago with 4-hour frequency is excluded (elapsed < interval − tolerance) in `src/tests/integration/test_scheduler_due_sources.py`
- [ ] T027 [US3] Integration test: an inactive source is excluded from `get_active_due()` regardless of last_scraped_at in `src/tests/integration/test_scheduler_due_sources.py`
- [ ] T028 [US3] Integration test: `mark_scraped()` sets `last_scraped_at` to the current time and commits in `src/tests/integration/test_scheduler_due_sources.py`
- [ ] T029 [US3] Integration test: CollectionPipeline.run() with no due sources publishes PipelineCompletedEvent and returns 0 in `src/tests/integration/test_scheduler_due_sources.py`

**Checkpoint**: US3 fully verified — due-source selection matches spec

---

## Phase 6: User Story 4 - Run Observability & Teardown (Priority: P3)

**Goal**: Verify that each run emits correlation-bounded logs, increments OTel counters, records duration, and flushes observability even on error.

**Independent Test**: Run `make test` and verify log binding, Sentry initialization, OTel flush, and duration recording.

### Verification Tests for User Story 4

- [ ] T030 [P] [US4] Test that `main()` binds a unique correlation_id to structlog context that persists across all log calls within the run in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T031 [P] [US4] Test that Sentry is initialized at import time with traces_sample_rate=0.1 when SENTRY_DSN is set in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T032 [P] [US4] Test that Sentry is NOT initialized when SENTRY_DSN is not set in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T033 [P] [US4] Test that `push_metrics()` failure does not prevent `shutdown_tracing()` from being called in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T034 [P] [US4] Test that `shutdown_tracing()` failure does not prevent process exit in `src/tests/unit/entrypoints/cli/test_main.py`

**Checkpoint**: US4 fully verified — observability and teardown match spec

---

## Phase 7: User Story 5 - Signal Handling & Hard Timeout (Priority: P3)

**Goal**: Verify that signal handlers log and set the flag but do NOT interrupt pipeline execution, and that `check_timeout()` exists but is never called in the runtime path.

**Independent Test**: Run `make test` and verify signal handler behavior and timeout function behavior.

### Verification Tests for User Story 5

- [ ] T035 [P] [US5] Test that `signal_handler` sets `_shutdown_requested = True` and logs `shutdown_signal_received` in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T036 [P] [US5] Test that `_shutdown_requested` is not checked by `CollectionPipeline.run()` (pipeline continues after signal) in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T037 [P] [US5] Test that `check_timeout()` returns True when elapsed >= 3000 seconds in `src/tests/unit/entrypoints/cli/test_main.py` (already exists — verify it still passes)
- [ ] T038 [P] [US5] Test that `check_timeout()` returns False when elapsed < 3000 seconds in `src/tests/unit/entrypoints/cli/test_main.py` (already exists — verify it still passes)
- [ ] T039 [US5] Test that `check_timeout()` is NOT called anywhere in `main()` execution path (verify by mocking and asserting zero calls) in `src/tests/unit/entrypoints/cli/test_main.py`

**Checkpoint**: US5 fully verified — signal and timeout scaffolding matches spec

---

## Phase 8: User Story 6 - Standalone Translation Pipeline (Priority: P4)

**Goal**: Verify that `build_translation_pipeline()` returns a dict with the expected keys and that translation runs independently of collection.

**Independent Test**: Run `make test` and verify `build_translation_pipeline()` output structure.

### Verification Tests for User Story 6

- [ ] T040 [P] [US6] Test that `build_translation_pipeline()` returns a dict with keys: use_case, tag_use_case, session, analyses_translation_repository, tag_translation_repository in `src/tests/unit/test_composition_root.py`
- [ ] T041 [US6] Test that `build_translation_pipeline()` does not create an InMemoryEventBus or notification handler in `src/tests/unit/test_composition_root.py`

**Checkpoint**: US6 fully verified — standalone translation pipeline matches spec

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story verification and cleanup.

- [ ] T042 [P] Add test for `CollectionPipeline.run()` that verifies `mark_scraped()` is called for each due setting after discovery in `src/tests/unit/infrastructure/collection/test_collection_pipeline.py`
- [ ] T043 [P] Add test for `CollectionPipeline.run()` that verifies pre-fetch dedup filter checks URL hashes against already-analyzed articles in `src/tests/unit/infrastructure/collection/test_collection_pipeline.py`
- [ ] T044 [P] Add test for `CollectionPipeline.run()` that verifies post-fetch dedup removes duplicate URLs in `src/tests/unit/infrastructure/collection/test_collection_pipeline.py`
- [ ] T045 Add test verifying that `main()` initializes the default HTTP client via `init_default_client(HttpClient.build_default())` in `src/tests/unit/entrypoints/cli/test_main.py`
- [ ] T046 Run `make test` and verify all unit tests pass
- [ ] T047 Run `make test-integration` and verify all integration tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–8)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (different test files)
  - US3 depends on integration test conftest from Setup (T002)
  - US4 depends on US1 test infrastructure (conftest.py from T001)
  - US5 depends on US1 test infrastructure (conftest.py from T001)
  - US6 is independent of US1–US5 (different file: test_composition_root.py)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 1 + Phase 2 — no dependencies on other stories
- **US2 (P2)**: Depends on Phase 1 + Phase 2 — independent of US1
- **US3 (P2)**: Depends on Phase 1 (T002) + Phase 2 — independent of US1/US2
- **US4 (P3)**: Depends on Phase 1 (T001) + Phase 2 — reuses US1 conftest
- **US5 (P3)**: Depends on Phase 1 (T001) + Phase 2 — reuses US1 conftest
- **US6 (P4)**: Depends on Phase 1 + Phase 2 — independent of US1–US5

### Within Each User Story

- Tests within a story marked [P] can run in parallel
- Each test is self-contained with its own mocks/fixtures

### Parallel Opportunities

- T001 and T002 can run in parallel (different conftest files)
- T003 and T004 can run in parallel (same file, different test functions)
- T015–T021 can all run in parallel (independent event bus wiring tests)
- T024–T029 run sequentially (integration tests with shared DB state)
- T030–T034 can run in parallel (independent observability tests)
- T035–T039 can run in parallel (independent signal/timeout tests)
- T040–T041 can run in parallel (independent translation pipeline tests)
- T042–T044 can run in parallel (independent pipeline behaviour tests)

---

## Parallel Example: User Story 1

```bash
# These can all be implemented in parallel (different test cases, same file):
Task T005: "Test main() raises ValueError when DATABASE_URL not set"
Task T006: "Test main() calls time.sleep() in [0, 180] when RUN_IMMEDIATELY not set"
Task T007: "Test main() does NOT call time.sleep() when RUN_IMMEDIATELY set"
Task T008: "Test main() generates run_id and correlation_id"
Task T009: "Test main() registers SIGTERM/SIGINT handlers"
Task T010: "Test main() calls build_collection_pipeline() then pipeline.run()"
Task T011: "Test main() calls push_metrics/shutdown_tracing in finally on error"
Task T012: "Test main() increments SCRAPER_RUNS counter"
Task T013: "Test main() records SCRAPER_DURATION histogram"
Task T014: "Test main() starts OTel span scraper.run"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T004)
3. Complete Phase 3: User Story 1 (T005–T014)
4. **STOP and VALIDATE**: `make test` — all US1 tests pass
5. Entry point lifecycle is now verified

### Incremental Delivery

1. Setup + Foundational → Test infrastructure ready
2. Add US1 → Verify entry point lifecycle (MVP!)
3. Add US2 → Verify composition root wiring
4. Add US3 → Verify due-source selection (integration)
5. Add US4 → Verify observability and teardown
6. Add US5 → Verify signal/timeout scaffolding
7. Add US6 → Verify standalone translation pipeline
8. Add Polish → Cross-cutting tests and final validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (test_main.py) + US4 (test_main.py) + US5 (test_main.py)
   - Developer B: US2 (test_composition_root.py) + US6 (test_composition_root.py)
   - Developer C: US3 (integration tests)
3. Stories complete and integrate independently

---

## Notes

- This is a **brownfield** feature: tasks write verification tests, not implementation code
- All existing tests must continue to pass (no regressions)
- Integration tests (US3) require `make test-integration` with a running PostgreSQL
- Unit tests must NOT require a database (constitution principle III)
- The conftest.py fixtures must mock all side effects (sleep, signals, DB, OTel)
- The existing `inspect.getsource()` tests in test_composition_root.py should be preserved; new behavioural tests are added alongside
