# Phase 1 Data Model: Redis Caching Layer for Read APIs

None of these entities are persisted in PostgreSQL or backed by an Alembic migration — they exist only as Redis keys/values and in-memory dataclasses. They're documented here because the spec's "Key Entities" section names them conceptually and the plan needs to pin down their concrete shape.

## Cache Namespace

One per cached read-endpoint family. Fixed, small set — not user-extensible.

| Namespace | Backs endpoint(s) | Bumped by |
|---|---|---|
| `articles` | `GET /articles`, `GET /articles/{article_id}` (static shape only — see below) | `PipelineCompletedEvent` handler; `topics.py` write endpoints (topic scoping affects article filtering); `tag_service.py` write functions (tag renames/merges affect filter values) |
| `graph` | `GET /analyses/graph` | Same triggers as `articles` (same underlying data) |
| `tag_groups` | `GET /tag-groups`, `GET /tag-groups/{group_id}` | `tag_service.py` write functions; `topics.py` write endpoints (topic-scoped tag groups) |
| `weekly_reports` | `/weekly-reports/*` | `PipelineCompletedEvent`-adjacent — actually triggered by the weekly report job's own completion, not the main scrape pipeline (see Assumptions below) |

## Cache Namespace Version (Redis key)

- **Key**: `cache:v:{namespace}` (e.g. `cache:v:articles`)
- **Value**: a plain integer, starting at `1` if absent (`INCR` on a missing key initializes to `1` in Redis, which is exactly the desired "no cache yet" starting state)
- **Written by**: `CacheGateway.bump_version(namespace)` → `INCR cache:v:{namespace}`
- **Read by**: `CacheGateway.get_or_set(namespace, params, ttl, loader)` to compute the current key prefix before every read
- **Redis DB**: `CACHE_REDIS_URL` (db 1) — a separate logical Redis DB from `REDIS_URL` (db 0, used by the unrelated view-count write-behind buffer and chat rate-limit counters). See research.md "Decision: `CACHE_REDIS_URL`".

## Cached View Response (Redis key)

- **Key shape**: `{namespace}:v{version}:{lang}:{param_hash}`
  - `version` — the namespace's current version at the time this entry was written (see above)
  - `lang` — the request's resolved language (`en` / `zh-TW`), since translated payloads differ
  - `param_hash` — a stable hash (e.g. `hashlib.sha1` of a canonical, sorted `repr`/JSON of the endpoint's query parameters) of everything that distinguishes one cached response from another for that endpoint (filters, sort, page, size, topic_id, etc.)
- **Value**: the JSON-serialized response payload (the same shape the endpoint would otherwise return)
- **TTL**: bounded (exact duration is an implementation/tasks-level tuning choice, not a spec-level decision — e.g. 24h as a safety net matching the daily refresh cadence; see FR-008). TTL exists purely as a missed-invalidation safety net — under normal operation, entries become unreachable (via the version bump) long before they'd expire.
- **Written by**: `CacheGateway.get_or_set(...)` on a cache miss (lazy, cache-aside)
- **Read by**: the four endpoint families in scope, on every request

### Article-detail entry — static/dynamic field split

`GET /articles/{article_id}`'s cached blob (`params: {"article_id": ..., "op": "detail"}`) contains every `ArticleDetailOut` field **except** `metrics` and `view_count`, which are always written as empty placeholders (`{}` / `0`) before caching. The router overwrites those two fields with a fresh, uncached query result (indexed lookups by `article_id` on `ArticleMetrics`/`ArticleMetricValue`) after every `get_or_set(...)` call, hit or miss. This is not TTL differentiation — the cached and uncached parts share the same `DEFAULT_TTL_SECONDS` safety net and the same `bump_version("articles")` invalidation trigger; only the *fields*, not the *duration*, are split. See research.md "Decision: Article-detail caching — static/dynamic field split, not a freshness-based TTL".

## Cache Warm-Up (eager re-population, not a stored entity)

After `CacheInvalidationHandler` bumps `cache:v:articles` / `cache:v:graph` on `PipelineCompletedEvent`, `CacheWarmupHandler` immediately re-populates the default (no-customization) reads via real HTTP calls to `backend`'s own endpoints, so the first visitor after a scrape run gets a cache hit instead of the guaranteed miss `bump_version` alone would leave behind. Warmed once with no `topic_id`, and once per active topic (`GET /topics`):

| Endpoint | Topic-less variant | Per-topic variant |
|---|---|---|
| `GET /articles` (default sort/page) | ✓ | ✓ |
| `GET /analyses/graph` (no filters) | ✓ | ✓ |
| `GET /tag-groups` (no filters) | ✓ | ✓ |
| `GET /weekly-reports/latest` | — (`topic_id` required) | ✓ |

Only these fixed default-parameter combinations are warmed — any user-customized filter/sort/pagination combination remains lazily populated via cache-aside on first request, same as before. See research.md "Decision: Eager cache warm-up after the scrape pipeline, via a real HTTP self-call to `backend`".

## Job Completion Notification Event

Two new dataclasses, structurally identical in shape to the existing `PipelineCompletedEvent` (`src/modules/collection/application/events/pipeline_completed.py`) but scoped to their own job's stats — they intentionally do **not** reuse `PipelineCompletedEvent` itself, since its `stats: List[SourceStats]` field is specific to per-source scrape counts and doesn't fit either job.

### `MetricsRefreshCompletedEvent`

`src/modules/collection/application/events/metrics_refresh_completed.py`

| Field | Type | Source |
|---|---|---|
| `total` | `int` | `len(rows)` in `refresh_metrics.py` |
| `refreshed` | `int` | existing `refreshed` count |
| `failed` | `int` | existing `failed` count |
| `duration_seconds` | `float` | existing `time.time() - start_time` |

### `RagBackfillCompletedEvent`

`src/modules/intelligence/application/events/rag_backfill_completed.py`

| Field | Type | Source |
|---|---|---|
| `total` | `int` | `len(articles)` in `backfill_rag.py` |
| `succeeded` | `int` | existing `succeeded` count |
| `failed` | `int` | existing `failed` count |
| `duration_seconds` | `float` | existing `time.time() - start_time` |

## Assumptions carried from spec.md, made concrete here

- `weekly_reports` namespace invalidation is triggered by the **weekly report job's own completion** (its existing per-report notification hook point inside `GenerateWeeklyReportUseCase`), not by the main scrape pipeline's `PipelineCompletedEvent` — the two jobs run on independent schedules and only the weekly report job actually writes `weekly_reports` rows.
- `articles` and `graph` namespaces share the same invalidation triggers because `graph_service.py`'s queries (`query_analyses`, `query_group_articles`) read from the exact same `Article`/`Analysis`/`Tag` tables as `article_service.py`'s `get_articles_paginated` — there is no scenario where one is stale and the other isn't.
- `scraper_keywords` and `scraper_settings` admin writes do **not** bump any of the four namespaces above — they configure *what the scraper collects next*, not any data currently rendered by the four cached read endpoints. No cache interaction needed for those two routers.
