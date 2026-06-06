# Feature Specification: Scheduler & Pipeline Assembly

**Feature Branch**: `007-scheduler-pipeline`

**Created**: 2026-05-29

**Status**: Brownfield (documents existing behaviour)

**Input**: The scheduling entry point and pipeline assembly capability. Covers the run-once CLI entry point with startup jitter, signal handling, hard timeout scaffolding, and observability teardown, as well as the dependency injection/composition root that wires the full scrape-to-notify pipeline.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scheduled Pipeline Run (Priority: P1)

An operator (or external scheduler such as Railway cron) invokes the scraper entry point. The system validates required configuration, applies a random startup delay to avoid synchronized load on upstream services, assembles the full collection pipeline, runs it to completion, and records observability data before exiting.

**Why this priority**: This is the core execution path — everything else exists to support or observe this run.

**Independent Test**: Can be fully tested by invoking the entry point with a valid `DATABASE_URL` and verifying the pipeline executes end-to-end, logs carry a correlation ID, and observability metrics are emitted.

**Acceptance Scenarios**:

1. **Given** `DATABASE_URL` is set and at least one scraper source is due, **When** the entry point is invoked, **Then** the pipeline discovers, fetches, processes, and analyzes articles, publishes a `PipelineCompletedEvent`, and exits with code 0.
2. **Given** `DATABASE_URL` is set and no scraper sources are due, **When** the entry point is invoked, **Then** the pipeline publishes `PipelineCompletedEvent` immediately with zero articles and exits cleanly.
3. **Given** `DATABASE_URL` is NOT set, **When** the entry point is invoked, **Then** the system raises an error before any pipeline assembly begins.
4. **Given** `RUN_IMMEDIATELY` is NOT set, **When** the entry point is invoked, **Then** the system sleeps for a random duration between 0 and 180 seconds before proceeding.
5. **Given** `RUN_IMMEDIATELY` is set to any value, **When** the entry point is invoked, **Then** the system skips the startup jitter sleep entirely.

---

### User Story 2 - Pipeline Assembly & Event Wiring (Priority: P2)

The composition root assembles all repositories, the in-process event bus, LLM services with rate limiting, use cases, and event handler subscriptions so that a scraped article flows through the full pipeline: scrape → dedup → process → analyze → normalize tags → translate → notify.

**Why this priority**: The wiring defines the entire data flow. Without correct assembly, no downstream capability works.

**Independent Test**: Can be tested by verifying that `build_collection_pipeline()` returns a pipeline whose event bus has the expected handler subscriptions and that calling `pipeline.run()` triggers the full chain when articles are discovered.

**Acceptance Scenarios**:

1. **Given** the database has active LLM providers configured, **When** `build_collection_pipeline()` is called, **Then** it returns a `CollectionPipeline` with a `ResilientLLMService` containing all active providers sorted by priority, each paired with a rate-limit strategy.
2. **Given** no active LLM providers exist in the database, **When** `build_collection_pipeline()` is called, **Then** it raises a `ValueError`.
3. **Given** the pipeline is assembled, **When** an `ArticleScrapedEvent` is published, **Then** the event bus dispatches it to `ArticleScrapedHandler`, which processes the article and publishes `ArticleProcessedEvent`.
4. **Given** an article has been analyzed, **When** `AnalysisCompletedEvent` is published, **Then** tag normalization runs, and upon completion, translation is triggered for each configured language.
5. **Given** any step in the pipeline fails (analysis, tag normalization, or translation), **When** the corresponding failed event is published, **Then** `FailedTaskPersistenceHandler` persists the failure as a `FailedTask` entity.

---

### User Story 3 - Due Source Selection (Priority: P2)

The pipeline determines which scraper sources are due for a run by checking their active status and whether enough time has elapsed since their last scrape, applying a tolerance window.

**Why this priority**: Source selection gates all pipeline activity — if no sources are due, the pipeline does no work.

**Independent Test**: Can be tested by setting up scraper sources with various `last_scraped_at` values and frequencies, then verifying that `get_active_due()` returns only the expected sources.

**Acceptance Scenarios**:

1. **Given** a scraper source is active and has never been scraped, **When** the pipeline checks for due sources, **Then** that source is included.
2. **Given** a scraper source is active and was last scraped 5 hours ago with a 4-hour frequency, **When** the pipeline checks for due sources, **Then** that source is included (elapsed time exceeds frequency minus 30-minute tolerance).
3. **Given** a scraper source is active and was last scraped 3.5 hours ago with a 4-hour frequency, **When** the pipeline checks for due sources, **Then** that source is NOT included (3.5h < 4h − 30min = 3.5h boundary; effectively excluded since elapsed must exceed the adjusted interval).
4. **Given** a scraper source is NOT active, **When** the pipeline checks for due sources, **Then** that source is excluded regardless of its last-scraped time.

---

### User Story 4 - Run Observability & Teardown (Priority: P3)

Each pipeline run emits structured log entries with a correlation ID, increments OpenTelemetry counters, records execution duration, and flushes all observability data before the process exits.

**Why this priority**: Observability is essential for production monitoring but does not affect the functional outcome of the pipeline.

**Independent Test**: Can be tested by running the entry point and verifying that log output contains `run_id` and `correlation_id` fields, the `SCRAPER_RUNS` counter increments, and the `SCRAPER_DURATION` histogram records a value.

**Acceptance Scenarios**:

1. **Given** the entry point starts, **When** the run context is initialized, **Then** a unique `run_id` and `correlation_id` are generated and bound to all subsequent log entries.
2. **Given** `SENTRY_DSN` is set, **When** the module is imported, **Then** Sentry is initialized with a trace sample rate of 10%.
3. **Given** `SENTRY_DSN` is NOT set, **When** the module is imported, **Then** Sentry is not initialized.
4. **Given** a pipeline run completes (successfully or with error), **When** the finally block executes, **Then** OTel metrics are flushed via `push_metrics()` and traces are flushed via `shutdown_tracing()`.
5. **Given** a pipeline run completes, **When** the finally block executes, **Then** the `SCRAPER_DURATION` histogram records the elapsed wall-clock time of the run.

---

### User Story 5 - Signal Handling & Hard Timeout (Priority: P3)

The system registers handlers for SIGTERM and SIGINT that log the signal and set a shutdown flag, and defines a 50-minute timeout check function, but neither mechanism currently interrupts pipeline execution.

**Why this priority**: These are scaffolding for future graceful shutdown. Documenting the current state (signals logged but not acted upon, timeout defined but not enforced) is important for brownfield accuracy.

**Independent Test**: Can be tested by sending SIGTERM to a running process and verifying that the signal handler logs a warning, and by calling `check_timeout()` with various elapsed times.

**Acceptance Scenarios**:

1. **Given** the entry point is running, **When** SIGTERM or SIGINT is received, **Then** the signal handler logs `shutdown_signal_received` with the signal number and sets the `_shutdown_requested` flag to `True`.
2. **Given** the `_shutdown_requested` flag is set, **When** the pipeline is running, **Then** the pipeline continues to completion (the flag is not checked by any pipeline component).
3. **Given** `check_timeout()` is called with an elapsed time of 3000 seconds or more, **Then** it returns `True`.
4. **Given** `check_timeout()` is called with an elapsed time less than 3000 seconds, **Then** it returns `False`.
5. **Given** the entry point is running, **When** 50 minutes have elapsed, **Then** the pipeline is NOT interrupted by the timeout mechanism (the function exists but is never called in the runtime path).

---

### User Story 6 - Standalone Translation Pipeline (Priority: P4)

A lighter assembly path allows running translation independently of the collection pipeline, enabling re-translation of existing analyses without re-scraping.

**Why this priority**: This is a secondary entry point used for maintenance/backfill, not the primary execution path.

**Independent Test**: Can be tested by calling `build_translation_pipeline()` and verifying it returns a dict containing the translation use case and required repositories.

**Acceptance Scenarios**:

1. **Given** the database has existing analyses, **When** `build_translation_pipeline()` is called, **Then** it returns a dict with `use_case`, `tag_use_case`, `session`, `analyses_translation_repository`, and `tag_translation_repository` keys.
2. **Given** a standalone translation run is invoked, **When** it completes, **Then** translations are persisted for each configured language without triggering scraping or analysis.

---

### Edge Cases

- What happens when the OTel push fails during teardown? → The `push_metrics()` and `shutdown_tracing()` calls are wrapped in try/except, so a flush failure does not prevent process exit.
- What happens when `DATABASE_URL` points to an unreachable database? → The pipeline will fail during `init_db()` or `get_session()` with a connection error; no special retry logic exists.
- What happens when all LLM providers' API keys are missing from the environment? → `build_llm_service()` reads each provider's `api_key_env` and looks up the corresponding environment variable; if the key is missing, the provider may fail on first use, and `ResilientLLMService` will fall back to the next provider.
- What happens when the startup jitter sleep is interrupted by a signal? → The `time.sleep()` call is not wrapped in signal-aware logic; the signal handler will set the flag, but the sleep will not be interrupted early.
- What happens when the same source is scraped twice in quick succession? → `mark_scraped()` sets `last_scraped_at`, and the next `get_active_due()` call will exclude it until the frequency interval (minus tolerance) has elapsed.
- What happens when `InMemoryEventBus` handler raises an exception? → The event bus propagates the exception synchronously, which can halt the pipeline run. There is no dead-letter or retry mechanism at the event bus level.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST validate that `DATABASE_URL` is set before any pipeline assembly begins.
- **FR-002**: The system MUST apply a random startup delay between 0 and 180 seconds unless the `RUN_IMMEDIATELY` environment variable is set.
- **FR-003**: The system MUST generate a unique `run_id` and `correlation_id` for each execution and bind them to all structured log output.
- **FR-004**: The system MUST assemble the full collection pipeline with all repositories, the in-process event bus, LLM services, use cases, and event handler subscriptions via the composition root.
- **FR-005**: The system MUST select only scraper sources that are active and due (never scraped or frequency interval elapsed minus 30-minute tolerance).
- **FR-006**: The system MUST execute the pipeline as a single run and exit — there is no in-process scheduler or loop.
- **FR-007**: The system MUST register signal handlers for SIGTERM and SIGINT that log the received signal.
- **FR-008**: The system MUST flush OpenTelemetry metrics and traces in a finally block after pipeline execution, regardless of success or failure.
- **FR-009**: The system MUST record the wall-clock duration of each run in an observability histogram.
- **FR-010**: The system MUST increment a `SCRAPER_RUNS` counter at the start of each execution.
- **FR-011**: The system MUST initialize Sentry at import time if `SENTRY_DSN` is set, with a trace sample rate of 10%.
- **FR-012**: The system MUST raise an error if no active LLM providers are configured in the database.
- **FR-013**: The system MUST persist failed tasks (analysis failure, tag normalization failure, translation failure, discover failure) via `FailedTaskPersistenceHandler`.
- **FR-014**: The system MUST provide a standalone translation pipeline assembly that returns a dict with use cases and repositories, independent of the collection pipeline.
- **FR-015**: The system MUST use a single database session (NullPool) for the entire pipeline lifecycle.

### Key Entities

- **Run Context**: The execution context for a single pipeline invocation, carrying a `run_id` and `correlation_id` bound to logs and traces.
- **ScraperSetting (Due Source)**: A configured scraper source with an active flag, frequency interval, and last-scraped timestamp. Due sources are selected by the pipeline before discovery.
- **CollectionPipeline**: The orchestrator that discovers due sources, runs the scrape executor, publishes events, and marks sources as scraped.
- **InMemoryEventBus**: Synchronous in-process event bus that dispatches domain events to registered handlers, forming the pipeline chain.
- **ResilientLLMService**: LLM service that holds an ordered list of provider-rate-limit pairs and falls back on exhaustion or error.
- **FailedTask**: A persisted record of a pipeline step failure (analysis, tag normalization, translation, or discover) for later retry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each pipeline run produces log output containing a unique `correlation_id` that is consistent across all log entries for that run.
- **SC-002**: The pipeline only scrapes sources that meet the due criteria (active + interval elapsed with tolerance), never re-scraping a source prematurely.
- **SC-003**: Every pipeline run emits the `SCRAPER_RUNS` counter increment and `SCRAPER_DURATION` histogram recording, regardless of whether articles are found.
- **SC-004**: All observability data (metrics and traces) is flushed before the process exits, even when the pipeline encounters an error.
- **SC-005**: A run with `RUN_IMMEDIATELY` set bypasses the startup jitter entirely, completing the configuration-to-execution transition without delay.
- **SC-006**: When no sources are due, the pipeline completes in under 5 seconds (no discovery, fetch, or processing overhead).
- **SC-007**: Failed tasks are persisted so that at least 95% of pipeline errors are recoverable via the retry mechanism.

## Assumptions

- The system relies on external scheduling (Railway cron, Kubernetes CronJob, system cron, or manual invocation) to trigger runs — there is no in-process scheduler.
- The startup jitter exists primarily to avoid synchronized load on arXiv's API at the top of the hour; other upstream services benefit incidentally.
- The 50-minute hard timeout (`check_timeout()`) and the `_shutdown_requested` signal flag are scaffolding for future graceful shutdown and are currently not enforced at runtime. This spec documents the current state.
- The single-session strategy (one SQLAlchemy session for the entire pipeline) means there is no per-article transaction isolation; a failure mid-pipeline does not roll back earlier work.
- The composition root reads LLM provider configuration from the database at assembly time; changing provider configuration requires a new pipeline run to take effect.
- The `InMemoryEventBus` is synchronous — all handlers execute in the same process and thread. Handler exceptions propagate and can halt the pipeline.
- Sentry initialization happens at module import time, not at pipeline run time; it applies to the entire process lifetime.
