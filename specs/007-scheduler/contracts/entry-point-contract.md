# Contracts: Scheduler & Pipeline Assembly

**Feature**: 007-scheduler-pipeline
**Date**: 2026-05-29

## Entry Point Contract

The scheduler entry point (`python -m src.entrypoints.cli.main`) is invoked by external schedulers. It has no CLI arguments — all configuration comes from environment variables and the database.

### Invocation Contract

| Aspect | Contract |
|--------|----------|
| Trigger | External (Railway cron, Docker, manual) |
| Arguments | None (no argparse) |
| Required env | `DATABASE_URL` |
| Optional env | `RUN_IMMEDIATELY`, `SENTRY_DSN`, `TRANSLATION_LANGUAGES` |
| Exit code 0 | Pipeline completed (with or without articles) |
| Exit code non-0 | Unhandled exception (config error, DB unreachable, etc.) |

### Lifecycle Contract

```
1. validate_config()           → raises ValueError if DATABASE_URL missing
2. configure_logging()        → structlog JSON + Loki
3. startup jitter             → 0-180s sleep (skip if RUN_IMMEDIATELY)
4. init HTTP client           → HttpClient.build_default()
5. increment SCRAPER_RUNS     → OTel counter
6. init run context           → run_id + correlation_id UUIDs
7. register signal handlers   → SIGTERM, SIGINT → log + set flag
8. start OTel span           → "scraper.run" with run.id, run.correlation_id
9. build_collection_pipeline → composition root
10. pipeline.run()            → returns article count
11. finally: record duration  → SCRAPER_DURATION histogram
12. finally: push_metrics()   → flush OTel metrics (wrapped in try/except)
13. finally: shutdown_tracing → flush OTel traces (wrapped in try/except)
```

### Error Propagation Contract

| Error Source | Behaviour |
|-------------|-----------|
| Missing `DATABASE_URL` | `ValueError` raised before pipeline assembly |
| No active LLM providers | `ValueError` raised in `build_llm_service()` |
| DB connection failure | Exception from `init_db()` / `get_session()`, unhandled |
| Pipeline step failure | `FailedTaskPersistenceHandler` persists failure; pipeline continues for other articles |
| Event handler exception | Propagates synchronously via `InMemoryEventBus`; can halt pipeline |
| OTel flush failure | Caught by try/except in finally block; does not prevent exit |

## Composition Root Contract

### `build_collection_pipeline() -> CollectionPipeline`

Returns a fully wired pipeline instance. Dependencies are resolved in this order:

1. DB session (single session, NullPool)
2. 10 repository instances (all sharing the session)
3. InMemoryEventBus
4. LLM services (from `llm_providers` DB table + env API keys)
5. Embedding services
6. Prompt factory
7. 5 use cases
8. 9 event handler subscriptions
9. ScrapeExecutor with discover-failed callback
10. ConcreteScraperFactory

Raises `ValueError` if no active LLM providers exist.

### `build_translation_pipeline() -> dict`

Returns `{"use_case", "tag_use_case", "session", "analyses_translation_repository", "tag_translation_repository"}`.

Lighter assembly — no event bus, no scraping, no notification wiring.

## Due Source Selection Contract

`get_active_due()` returns `ScraperSetting` rows where:
- `is_active = True`
- AND (`last_scraped_at IS NULL` OR `now() - last_scraped_at > interval_hours - 30min tolerance`)

`mark_scraped(setting_id)` sets `last_scraped_at = now()` and commits immediately.
