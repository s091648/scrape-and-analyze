# Implementation Plan: Redis Caching Layer for Read APIs

**Branch**: `020-redis-caching-layer` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/020-redis-caching-layer/spec.md`

## Summary

Add a shared, Redis-backed caching layer (`shared/cache/`) in front of four read-heavy backend endpoints (`/articles`, `/analyses/graph`, `/tag-groups`, `/weekly-reports`) that currently query PostgreSQL on every request, to improve frontend Web Vitals. Cache freshness is maintained by write-through invalidation from two sources: the daily scraper CLI pipeline (on `PipelineCompletedEvent`) and admin write endpoints (topics/tags/scraper-settings, synchronously after `db.commit()`). High-cardinality parameterized reads (article-list filters) use cache-aside with lazy population instead of precomputing every combination. No message queue or separate microservice is introduced — both the CLI process and the backend process call the same shared module directly against the one existing Redis instance. As a related, independently-testable piece of work, two CLI entrypoints that currently finish silently (`refresh_metrics.py`, `backfill_rag.py`) get the same job-completion notification pattern `main.py` already has.

## Technical Context

**Language/Version**: Python 3.11 (both `backend/` and `src/`); no frontend code changes required — Web Vitals improve as a side effect of faster API responses through the existing Next.js proxy.

**Primary Dependencies**: FastAPI, SQLAlchemy (unchanged); `redis` (>=5.0, already a dependency — sync `redis.Redis` client, not `redis.asyncio`, see research.md); existing `src/shared/application/ports/event_bus.py` `EventBus` Protocol + `InMemoryEventBus`; existing `NotificationHandler` / `TelegramNotifierClient` infra.

**Storage**: PostgreSQL (unchanged, remains source of truth) + Redis (already deployed; now used for query-result caching in addition to its existing view-count use in `articles.py`).

**Testing**: pytest — `backend/tests/` (router + service + `CacheGateway` unit tests, admin write-through behavior), `src/tests/unit/` (`RedisCacheGateway`, new event dataclasses, new message builders, notification wiring), `src/tests/integration/` (`@pytest.mark.integration`, real Redis via the `redis` service container) per Constitution Principle III.

**Target Platform**: Existing Docker Compose services — `backend`, `app`/`job_service` (CLI, already `depends_on: redis`). No new services, no `docker-compose.yml` changes needed.

**Project Type**: Web service (FastAPI backend) + scheduled CLI batch jobs (`src/entrypoints/cli/`), sharing one new cross-cutting module.

**Performance Goals**: Repeat reads of an already-seen parameter combination are served without a PostgreSQL round-trip (cache hit). No specific latency SLO was set by the user; success is measured qualitatively per spec.md SC-001 (measurably faster repeat views).

**Constraints**: Cache staleness after an admin write must be zero by the time that request's response is returned (synchronous invalidation). Cache staleness after the daily pipeline must be zero once `PipelineCompletedEvent` has been handled. If Redis is unavailable, every covered endpoint must still serve correct data from PostgreSQL (graceful degradation, Constitution Principle VI) — no request may fail because of the caching layer.

**Scale/Scope**: 4 read endpoint families; ~5 write call sites (CLI pipeline completion handler + `topics.py`, `tag_service.py`, `scraper_keyword_service.py`, `scraper_settings_service.py`); 2 CLI entrypoints gain notification wiring.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **Principle I (DDD, NON-NEGOTIABLE)** — PASS. `shared/cache/` sits outside `src/` (like `shared/llm_provider.py`), so the hexagonal-layering requirement doesn't apply to it directly. The one piece of new code that *does* live inside `src/` — `CacheInvalidationHandler`, subscribed to `PipelineCompletedEvent` — is a thin application-layer event handler, consistent with existing handlers (`AnalysisCompletedHandler`, etc.) under `src/modules/*/application/event_handlers/`.
- **Principle III (Test Discipline)** — PASS, with an explicit test-phase obligation carried into `tasks.md`: unit tests for `CacheGateway`/`RedisCacheGateway` key-building and version-bump logic (no real Redis needed — mock the client), integration tests behind `@pytest.mark.integration` exercising real cache-aside behavior against the `redis` service container, backend tests for admin write-through invalidation and cache-hit/miss on the four endpoints, and unit tests for the two new notification events/message builders (mirroring `test_pipeline_completed_message_builder.py`).
- **Principle IV (Docker-First)** — PASS. `redis` is already an always-on service; `app`/`job_service`/`test_service`/`backend` already `depends_on: redis` and load `env_file: .env`. No compose changes.
- **Principle VI (Observability)** — PASS. Cache read/write paths use existing structlog loggers (`get_logger(__name__)`); a Redis-unavailable condition must log a warning and fall through to the DB rather than raise, per the constitution's graceful-degradation rule for observability-adjacent infra. New CLI notification code follows the existing `with_span(...)` wrapping used for `PipelineCompletedEvent` handlers.
- **Principle VIII (UML Conventions)** — PASS. `CacheInvalidationHandler` follows the naming/`handle()`/`event_bus.subscribe()` convention. The two new CLI notification events (`MetricsRefreshCompletedEvent`, `RagBackfillCompletedEvent`) end in `Event`; their handlers are wired via `event_bus.subscribe()` in `bootstrap.py`, matching `main.py`'s existing pipeline so both jobs render correctly in the auto-generated diagram (see research.md's "Decision: CLI notification extension").
- **Principle IX (FastAPI Microservice Structure)** — PASS. `RedisCacheGateway` takes `redis_url` via constructor injection rather than reading `os.environ` itself, so `backend/config.py` remains the sole `os.environ` read point on the backend side (its existing `REDIS_URL` constant is reused, passed in at composition time). `src/config/settings.py` gains one new `REDIS_URL` constant (see research.md) to mirror this on the CLI side.

No violations requiring justification — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-redis-caching-layer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── cache-gateway.md
│   └── cli-notification-events.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
shared/
└── cache/
    ├── __init__.py            # exports CacheGateway, RedisCacheGateway, CacheNamespace
    ├── gateway.py              # CacheGateway (Protocol) — get_or_set(), bump_version()
    └── redis_gateway.py        # RedisCacheGateway — sync redis.Redis-backed implementation

backend/
├── config.py                                    # (existing REDIS_URL, reused)
├── routers/
│   ├── articles.py                              # list_articles: cache-aside via CacheGateway
│   ├── graph.py                                 # get_graph: replace in-process _cache dict
│   ├── tags.py                                  # list_tag_groups: cache-aside; write endpoints: bump_version
│   ├── topics.py                                # write endpoints: bump_version after db.commit()
│   ├── scraper_keywords.py                      # (unaffected directly — bump via scraper_keyword_service)
│   └── scraper_settings.py                      # (unaffected directly — bump via scraper_settings_service)
└── services/
    ├── article_service.py                       # cache-key param builder for get_articles_paginated
    ├── graph_service.py                         # cache-key param builder for query_analyses/query_group_articles
    ├── weekly_report_service.py                 # cache-aside wrapping for weekly report reads
    ├── tag_service.py                            # bump_version() calls on write functions
    ├── scraper_keyword_service.py                # bump_version() calls on write functions
    └── scraper_settings_service.py                # bump_version() calls on write functions

src/
├── config/settings.py                            # + REDIS_URL constant
├── bootstrap.py                                   # + CacheInvalidationHandler wiring on PipelineCompletedEvent;
│                                                   #   + event_bus + notification wiring in
│                                                   #   build_metrics_refresh_pipeline() / build_rag_backfill_pipeline()
├── modules/
│   ├── collection/application/
│   │   ├── events/metrics_refresh_completed.py    # new: MetricsRefreshCompletedEvent
│   │   └── event_handlers/cache_invalidation_handler.py  # new: CacheInvalidationHandler
│   └── intelligence/application/
│       └── events/rag_backfill_completed.py       # new: RagBackfillCompletedEvent
├── infrastructure/
│   ├── collection/notifications/
│   │   └── metrics_refresh_message_builder.py     # new
│   ├── intelligence/notifications/
│   │   └── rag_backfill_message_builder.py        # new
│   └── shared/notifications/
│       └── notification_service.py                # NotificationHandler type hints widened to Any
└── entrypoints/cli/
    ├── refresh_metrics.py                          # + publish MetricsRefreshCompletedEvent
    └── backfill_rag.py                             # + publish RagBackfillCompletedEvent
```

**Structure Decision**: Web-service + CLI hybrid (Option 2-like, but this repo's actual layout is `backend/` + `src/` + shared top-level `models/`/`shared/`, not the generic `backend/src/`+`frontend/src/` template). The new `shared/cache/` module is the only new cross-service directory; everything else is additive changes inside each service's existing structure, following each service's own established conventions (backend: routers thin, services hold logic; src: DDD modules + bootstrap composition root).
