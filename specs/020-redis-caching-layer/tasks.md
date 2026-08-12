---

description: "Task list for feature implementation"
---

# Tasks: Redis Caching Layer for Read APIs

**Input**: Design documents from `specs/020-redis-caching-layer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included per Constitution §III (mandatory, non-optional). Per this project's established working style, implementation tasks are listed before their corresponding test tasks within each story (tests validate what was just built, not written first — this is a deliberate, standing preference for this codebase, not an omission).

**Organization**: Tasks are grouped by user story (from spec.md, priority order P1 → P2 → P3 → P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 (faster browsing) / US2 (admin write-through) / US3 (daily pipeline write-through) / US4 (CLI notifications)

---

## Phase 1: Setup

**Purpose**: Scaffolding only — no new external dependencies (`redis>=5.0` is already in `pyproject.toml`; no `docker-compose.yml` changes needed, `app`/`job_service`/`backend`/`test_service` already `depends_on: redis`).

- [X] T001 Create `shared/cache/__init__.py`, `shared/cache/gateway.py`, `shared/cache/redis_gateway.py` as empty/skeleton files
- [X] T002 [P] Add `REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")` to `src/config/settings.py`, mirroring the existing constant in `backend/config.py` (research.md decision)

**Checkpoint**: Package skeleton exists; both services can resolve a Redis URL.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared `CacheGateway` contract and its Redis implementation — every user story below depends on this.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Define `CacheGateway` Protocol in `shared/cache/gateway.py` with `get_or_set(namespace, params, ttl_seconds, loader, lang="en")` and `bump_version(namespace)` per `contracts/cache-gateway.md`
- [X] T004 Implement `RedisCacheGateway` in `shared/cache/redis_gateway.py`: constructor takes `redis_url: str` (no internal `os.environ` reads), uses sync `redis.Redis.from_url(...)` (research.md — not `redis.asyncio`), builds keys as `{namespace}:v{version}:{lang}:{param_hash}` (canonical sorted-JSON hash of `params`, per data-model.md), reads the namespace version via `cache:v:{namespace}` before every `get_or_set`, and implements `bump_version` via `INCR cache:v:{namespace}`
- [X] T005 Add graceful-degradation behavior to `RedisCacheGateway`: catch `redis.exceptions.RedisError` (connection errors) in both methods, log a warning via `get_logger(__name__)`, and fall through to calling `loader()` uncached (`get_or_set`) or no-op (`bump_version`) — never raise to the caller (FR-009, Constitution Principle VI)
- [X] T006 [P] Export `CacheGateway`, `RedisCacheGateway` from `shared/cache/__init__.py`
- [X] T007 [P] Unit tests for `RedisCacheGateway` in `backend/tests/test_shared_cache_gateway.py` (mocked `redis.Redis` client, no real Redis) — cover: cache miss calls loader and writes; cache hit skips loader; different `params` produce different keys; `bump_version` orphans the previous key; `RedisError` on either method falls through without raising
- [X] T008 [P] Integration test for `RedisCacheGateway` in `backend/tests/integration/test_shared_cache_gateway.py` (`@pytest.mark.integration`, real `redis` service container) — cover the same behaviors as T007 end-to-end against real Redis

**Checkpoint**: `CacheGateway`/`RedisCacheGateway` fully implemented and tested — user story implementation can now begin.

---

## Phase 3: User Story 1 - Faster browsing of articles, graph, tags, and weekly reports (Priority: P1) 🎯 MVP

**Goal**: Repeat reads of the same parameters for `/articles`, `/analyses/graph`, `/tag-groups`, `/weekly-reports` are served from Redis instead of PostgreSQL.

**Independent Test**: Per quickstart.md §1 — call each endpoint twice with identical params, confirm the second call doesn't hit the DB (verified via Redis `KEYS` inspection and/or query-count assertions in tests) and is measurably faster.

### Implementation for User Story 1

- [X] T009 [US1] Wire a `CacheGateway` instance into backend dependency injection (construct `RedisCacheGateway(redis_url=REDIS_URL)` once, expose via a FastAPI dependency or module-level singleton, following the existing pattern of module-level construction already used for Redis in `backend/routers/articles.py`)
- [X] T010 [US1] Wrap `get_articles_paginated` in `backend/services/article_service.py` with `CacheGateway.get_or_set("articles", params, ttl_seconds, loader, lang)`, where `params` is a dict of every filter/sort/pagination argument the function currently accepts
- [X] T011 [US1] Wrap `query_analyses`/`query_group_articles` + `build_graph` result in `backend/services/graph_service.py` with `CacheGateway.get_or_set("graph", params, ttl_seconds, loader, lang)`, and delete the existing in-process `_cache`/`CACHE_TTL_SECONDS` dict-based caching in `backend/routers/graph.py` (research.md — replaced, not kept alongside)
- [X] T012 [P] [US1] Wrap `list_tag_groups`/`get_tag_group` reads in `backend/routers/tags.py` (or a new read function in `backend/services/tag_service.py`) with `CacheGateway.get_or_set("tag_groups", params, ttl_seconds, loader, lang)`
- [X] T013 [P] [US1] Wrap `get_weekly_reports`, `get_latest_weekly_report`, `get_weekly_report_by_week`, `get_weekly_report_weeks` in `backend/services/weekly_report_service.py` with `CacheGateway.get_or_set("weekly_reports", params, ttl_seconds, loader, lang)`

### Tests for User Story 1

- [X] T014 [P] [US1] Integration tests in `backend/tests/integration/test_articles.py` asserting a second identical `GET /articles` request does not issue a new DB query (e.g. via SQLAlchemy query-count assertion or a mocked/spied `get_articles_paginated`)
- [X] T015 [P] [US1] Integration tests in `backend/tests/integration/test_graph.py` asserting the same cache-hit behavior for `GET /analyses/graph`, and that the old in-process `_cache` dict no longer exists (import-level assertion or behavior test confirming cache is now shared/keyed by `CacheGateway`)
- [X] T016 [P] [US1] Integration tests in `backend/tests/integration/test_tags.py` asserting cache-hit behavior for `GET /tag-groups`
- [X] T017 [P] [US1] Integration tests in a weekly-reports test file (e.g. `backend/tests/integration/test_weekly_reports.py`, creating it if it doesn't already exist) asserting cache-hit behavior for the weekly-reports endpoints

**Checkpoint**: User Story 1 fully functional and independently testable/demoable — this alone is the MVP for the Web Vitals goal.

---

## Phase 4: User Story 2 - Admin changes are visible immediately (Priority: P2)

**Goal**: Admin writes to topics/tags synchronously invalidate the cache namespaces they affect, so the very next read reflects the change.

**Independent Test**: Per quickstart.md §2 — edit a tag via the admin API, confirm `cache:v:tag_groups` incremented and the next `GET /tag-groups` reflects the change.

### Implementation for User Story 2

- [X] T018 [US2] Add `CacheGateway.bump_version("articles")`, `bump_version("graph")`, `bump_version("tag_groups")` calls after `db.commit()` in `backend/routers/topics.py`'s create/update/delete endpoints (research.md — topics has no service layer, so the call lives directly in the router, matching that file's existing style)
- [X] T019 [P] [US2] Add `CacheGateway.bump_version("articles")`, `bump_version("graph")`, `bump_version("tag_groups")` calls to the write functions in `backend/services/tag_service.py` (rename, delete, merge, batch-move, approve/reject suggestion)

### Tests for User Story 2

- [X] T020 [P] [US2] Integration test in `backend/tests/integration/test_topics.py`: edit/delete a topic, assert `cache:v:articles`/`cache:v:graph`/`cache:v:tag_groups` all incremented and a subsequent read reflects the change
- [X] T021 [P] [US2] Integration test in `backend/tests/integration/test_tags.py`: rename/delete a tag, assert the relevant namespace versions incremented and `GET /tag-groups` reflects the change on the very next call

**Checkpoint**: User Stories 1 AND 2 both work independently — admin edits are no longer masked by stale cache.

---

## Phase 5: User Story 3 - Freshly scraped content appears without manual intervention (Priority: P3)

**Goal**: The daily scrape pipeline and the weekly report job each bump their relevant cache namespaces on completion, with no manual cache-clearing step.

**Independent Test**: Per quickstart.md §3 — run the scrape pipeline, confirm `cache:v:articles`/`cache:v:graph` incremented and new articles appear in the next read.

### Implementation for User Story 3

- [X] T022 [US3] Create `CacheInvalidationHandler` in `src/modules/collection/application/event_handlers/cache_invalidation_handler.py`: `handle(event: PipelineCompletedEvent)` calls `CacheGateway.bump_version("articles")` and `bump_version("graph")`
- [X] T023 [US3] Wire `CacheInvalidationHandler` in `src/bootstrap.py`'s `build_collection_pipeline()`: construct `RedisCacheGateway(redis_url=REDIS_URL)`, instantiate the handler, and `event_bus.subscribe(PipelineCompletedEvent, cache_invalidation_handler.handle)` alongside the existing `otel_handler`/`notification_handler` subscriptions (same `PipelineCompletedEvent` subscriber block, `src/bootstrap.py` ~line 406-413)
- [X] T024 [US3] Add a `CacheGateway.bump_version("weekly_reports")` call at the weekly report job's existing completion point in `src/modules/intelligence/application/use_cases/generate_weekly_report.py` (`GenerateWeeklyReportUseCase`), and wire a `RedisCacheGateway` instance into `build_weekly_pipeline()` in `src/bootstrap.py`

### Tests for User Story 3

- [X] T025 [P] [US3] Unit test `CacheInvalidationHandler` in `src/tests/unit/modules/collection/application/test_cache_invalidation_handler.py` (mirroring `test_otel_metrics_handler.py`'s shape) — asserts `bump_version` is called for both `articles` and `graph` namespaces on a `PipelineCompletedEvent`
- [X] T026 [P] [US3] Integration test confirming `build_collection_pipeline()` wires `CacheInvalidationHandler` to `PipelineCompletedEvent` (extend `src/tests/unit/test_composition_root.py`, following its existing assertion style for other handlers)
- [X] T027 [P] [US3] Unit/integration test for `GenerateWeeklyReportUseCase` confirming `bump_version("weekly_reports")` fires on successful report generation

**Checkpoint**: All three caching user stories (US1-US3) work together — reads are fast, admin edits and scheduled data changes are both reflected immediately.

---

## Phase 6: User Story 4 - Operators are notified when metrics-refresh and RAG-backfill jobs finish (Priority: P3)

**Goal**: `refresh_metrics.py` and `backfill_rag.py` send a completion notification, matching the existing `main.py` pattern.

**Independent Test**: Per quickstart.md §5 — run each job, confirm a Telegram completion message arrives.

### Implementation for User Story 4

- [X] T028 [US4] Widen `NotificationHandler`'s type hints from `PipelineCompletedEvent` to `Any` in `src/infrastructure/shared/notifications/notification_service.py`, and change `build_notification_handler()` to accept a `message_builder` parameter instead of hardcoding `PipelineCompletedMessageBuilder` (per `contracts/cli-notification-events.md`); update `main.py`'s/`bootstrap.py`'s existing call site to `build_notification_handler(PipelineCompletedMessageBuilder)`
- [X] T029 [P] [US4] Create `MetricsRefreshCompletedEvent` dataclass (`total: int, refreshed: int, failed: int, duration_seconds: float`) in `src/modules/collection/application/events/metrics_refresh_completed.py`, per data-model.md
- [X] T030 [P] [US4] Create `RagBackfillCompletedEvent` dataclass (`total: int, succeeded: int, failed: int, duration_seconds: float`) in `src/modules/intelligence/application/events/rag_backfill_completed.py`, per data-model.md
- [X] T031 [P] [US4] Create `MetricsRefreshMessageBuilder` in `src/infrastructure/collection/notifications/metrics_refresh_message_builder.py`, mirroring `PipelineCompletedMessageBuilder`'s MarkdownV2/`_esc`/footer conventions but rendering a flat total/refreshed/failed summary
- [X] T032 [P] [US4] Create `RagBackfillMessageBuilder` in `src/infrastructure/intelligence/notifications/rag_backfill_message_builder.py`, same conventions, rendering total/succeeded/failed
- [X] T033 [US4] In `src/bootstrap.py`'s `build_metrics_refresh_pipeline()`: construct an `InMemoryEventBus`, `event_bus.subscribe(MetricsRefreshCompletedEvent, build_notification_handler(MetricsRefreshMessageBuilder).handle)`, and return the event bus alongside the existing `(metrics_service, metrics_repo, session)` tuple
- [X] T034 [US4] In `src/bootstrap.py`'s `build_rag_backfill_pipeline()`: same wiring for `RagBackfillCompletedEvent`/`RagBackfillMessageBuilder`, returned alongside `(use_case, backfill_repo, session)`
- [X] T035 [US4] Update `src/entrypoints/cli/refresh_metrics.py`'s `main()` to unpack the new `event_bus` return value and `event_bus.publish(MetricsRefreshCompletedEvent(total=len(rows), refreshed=refreshed, failed=failed, duration_seconds=...))` after the existing `logger.info("metrics_refresh_completed", ...)` call
- [X] T036 [US4] Update `src/entrypoints/cli/backfill_rag.py`'s `main()` to unpack the new `event_bus` return value and `event_bus.publish(RagBackfillCompletedEvent(total=len(articles), succeeded=succeeded, failed=failed, duration_seconds=...))` after the existing `logger.info("rag_backfill_completed", ...)` call

### Tests for User Story 4

- [X] T037 [P] [US4] Unit test for `NotificationHandler`'s widened type hints and `build_notification_handler(message_builder)` parameterization in `src/tests/unit/infrastructure/shared/notifications/test_notification_build.py` (extend existing file) — confirm `main.py`'s existing behavior is unchanged (regression) and the new parameterized form works with an arbitrary message builder
- [X] T038 [P] [US4] Unit test `MetricsRefreshMessageBuilder` in `src/tests/unit/infrastructure/collection/notifications/test_metrics_refresh_message_builder.py`, mirroring `test_pipeline_completed_message_builder.py`
- [X] T039 [P] [US4] Unit test `RagBackfillMessageBuilder` in `src/tests/unit/infrastructure/intelligence/notifications/test_rag_backfill_message_builder.py`, same shape
- [X] T040 [US4] Integration/unit test confirming `refresh_metrics.py`'s `main()` publishes `MetricsRefreshCompletedEvent` with correct counts, and that a sender exception (simulated Telegram failure) does not raise out of `main()` (FR-012)
- [X] T041 [US4] Integration/unit test confirming `backfill_rag.py`'s `main()` publishes `RagBackfillCompletedEvent` with correct counts and the same failure-isolation behavior (FR-012)

**Checkpoint**: All four user stories complete and independently verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T042 [P] Choose and document the TTL value(s) used as the missed-invalidation safety net (data-model.md leaves the exact duration as a tuning choice) as a named constant per namespace, e.g. in `shared/cache/gateway.py`
- [ ] T043 Run through `quickstart.md` end-to-end manually (all 5 sections) against `docker compose up`, confirming every step's expected behavior
- [ ] T044 [P] Update `site/guide/architecture/` docs (or run whatever generator is appropriate) if the new `CacheInvalidationHandler`/events change the auto-generated UML pipeline diagram (Constitution Principle VIII — `make uml-backend`)

**Checkpoint**: MVP through US4 complete. Phase 8 below covers post-review refinements identified after the initial implementation.

---

## Phase 8: Post-Implementation Refinements

**Purpose**: Three follow-ups identified in review, after the four user stories above were already implemented: (1) `cache_gateway` wasn't actually DI-friendly despite `T009` allowing either approach, (2) cache-aside shared a Redis DB with unrelated durable state, (3) the design left a guaranteed cache-miss on the very first request after every scrape run, and article-detail reads were never wrapped at all. None of these change the `CacheGateway` contract (`contracts/cache-gateway.md` is still accurate) — see research.md's four new "Decision" entries for full rationale.

- [X] T045 Convert `backend/cache.py`'s `cache_gateway` from a bare module-level import to FastAPI `Depends()`: add `get_cache_gateway()` accessor; every router that reads or writes it (`articles.py`, `graph.py`, `tags.py`, `weekly_reports.py`, `topics.py`) takes `cache_gateway: CacheGateway = Depends(get_cache_gateway)`; `tags.py`/`topics.py`'s shared bump helpers take `cache_gateway` as an explicit parameter (can't receive `Depends()` themselves)
- [X] T046 [P] Update tests that previously patched the module-level `cache_gateway` attribute (`test_graph.py`, `test_graph_similarity.py` → `app.dependency_overrides[get_cache_gateway]`; `test_topics.py`, `test_tags.py` → `from backend.cache import cache_gateway` directly, since the singleton object itself is unchanged)
- [X] T047 Add `CACHE_REDIS_URL` (default `redis://redis:6379/1`) to `backend/config.py` and `src/config/settings.py`, distinct from the existing `REDIS_URL` (db 0); rewire `backend/cache.py` and both `RedisCacheGateway(...)` construction sites in `src/bootstrap.py` (`CacheInvalidationHandler`, `GenerateWeeklyReportUseCase`) to use it; document in `.env.example`
- [X] T048 Create `CacheWarmupHandler` (`src/modules/collection/application/event_handlers/cache_warmup_handler.py`): on `PipelineCompletedEvent`, fetches a guest token (`POST /auth/guest`) and re-populates the default-parameter reads (`GET /articles`, `/analyses/graph`, `/tag-groups` topic-less and per active topic; `/weekly-reports/latest` per active topic) via real HTTP calls to `backend`'s own endpoints — never duplicates backend's query-building logic. All requests independently fail-soft (log + continue), matching FR-009's graceful-degradation posture
- [X] T049 Add `BACKEND_URL` setting to `src/config/settings.py` (default `http://backend:8000`, mirrors frontend's existing `BACKEND_URL` convention); wire `CacheWarmupHandler` in `src/bootstrap.py`'s `build_collection_pipeline()`, subscribed to `PipelineCompletedEvent` *immediately after* `cache_invalidation_handler` (subscription order is load-bearing — `InMemoryEventBus` dispatches in `subscribe()`-call order, and warming must target the version `bump_version()` just created)
- [X] T050 Wrap `GET /articles/{article_id}` (`backend/routers/articles.py`'s `get_article`) in `cache_gateway.get_or_set("articles", {"article_id": ..., "op": "detail"}, DEFAULT_TTL_SECONDS, _load, lang=lang)` — `_load()` returns every `ArticleDetailOut` field except `metrics`/`view_count` (placeholders), which are always re-queried fresh (uncached, indexed PK lookups) and merged in after the cache read. No age-based TTL — see research.md
- [X] T051 [P] Unit tests for `CacheWarmupHandler` (`src/tests/unit/modules/collection/application/test_cache_warmup_handler.py`, mocked `requests`) — cover: topic-less + per-topic default warming, guest-token failure doesn't raise, a single warm request failing doesn't abort the rest
- [X] T052 [P] Extend `src/tests/unit/test_composition_root.py`: `PipelineCompletedEvent` now has 4 handlers (was 3); assert `CacheWarmupHandler` is subscribed and registered strictly after `CacheInvalidationHandler`
- [X] T053 Update `quickstart.md` for the DB split (`redis-cli -n 1 KEYS ...` instead of unqualified `KEYS`) and add a warm-up verification step (run `main.py`, confirm `/articles`/`/analyses/graph`/`/tag-groups` are already cache-hits on the *first* request afterward, with no prior manual `curl`)

**Checkpoint**: `cache_gateway` is DI-friendly and independently testable; cache-aside and durable operational state (view counts, rate limits) can never collide on a shared `FLUSHDB`; the default reads most users hit are warm immediately after every scrape run; article detail pages are cached with zero staleness risk on `view_count`/`metric_values`.

---

## Phase 9: `X-Cache` Response Header + Redis Eviction Policy (Post-Ship Addendum)

**Purpose**: Two follow-ups raised after Phase 8 shipped — a CloudFront-style `X-Cache: HIT|MISS|BYPASS` header on every cache-aside-backed endpoint, and a `maxmemory`/eviction policy for the `redis` service (previously unset — Redis 7 defaults to unlimited memory + `noeviction`). See research.md's "Post-Ship Addendum" for full rationale and `contracts/cache-gateway.md`'s addendum for the updated `CacheGateway` interface.

- [X] T054 Add `CacheResult` frozen dataclass (`value: Any`, `status: Literal["HIT", "MISS", "BYPASS"]`) to `shared/cache/gateway.py`; change `CacheGateway.get_or_set()`'s Protocol return type from `Any` to `CacheResult`; export `CacheResult` from `shared/cache/__init__.py`
- [X] T055 Update `RedisCacheGateway.get_or_set()` in `shared/cache/redis_gateway.py` to wrap all three return paths in `CacheResult`: cache hit → `status="HIT"`, loader ran + cache write → `status="MISS"`, `RedisError` fallback → `status="BYPASS"`
- [X] T056 [P] Update `backend/routers/articles.py`'s two `get_or_set` call sites (`list_articles`, `get_article`): add `response: Response` parameter, unpack `result.value`/`result.status`, set `response.headers["X-Cache"] = result.status`, return `result.value` (for `get_article`, merge `metrics`/`view_count` into `result.value` before returning, same as today)
- [X] T057 [P] Update `backend/routers/graph.py`'s `get_graph` the same way
- [X] T058 [P] Update `backend/routers/tags.py`'s `list_tag_groups`/`get_tag_group` the same way
- [X] T059 [P] Update `backend/routers/weekly_reports.py`'s four read endpoints the same way
- [X] T060 Update every fake/mock `CacheGateway` in tests to return `CacheResult` instead of a bare value: `backend/tests/conftest.py`'s `_NoCacheGateway`, `backend/tests/test_graph.py`/`test_graph_similarity.py`'s fake gateways, `backend/tests/test_shared_cache_gateway.py`, `backend/tests/integration/test_shared_cache_gateway.py`
- [X] T061 [P] Unit/integration tests asserting `X-Cache: HIT` on a repeat request, `X-Cache: MISS` on first request, and `X-Cache: BYPASS` when the cache gateway is unavailable, for at least one endpoint per router (`articles`, `graph`, `tags`, `weekly_reports`)
- [X] T062 Add `command: redis-server --maxmemory 256mb --maxmemory-policy volatile-lru` to the `redis` service in `docker-compose.yml` (**local dev/test only** — see T062a for why this doesn't cover production)
- [ ] T062a **[MANUAL, not a code change — still pending]** Set the Start Command on Railway's production `redis` service (and staging's, if it provisions its own) to `/opt/bitnami/scripts/redis/entrypoint.sh /opt/bitnami/scripts/redis/run.sh --maxmemory 256mb --maxmemory-policy volatile-lru` via the Railway dashboard — `postgres`/`redis` are intentionally excluded from this repo's `railway.toml`/CI deploy pipeline (`site/guide/deployment.md` §2), so there is no PR or tag push that reaches this service; whoever has Railway project access must apply it directly. A `redis-cli CONFIG SET maxmemory 256mb` / `CONFIG SET maxmemory-policy volatile-lru` against the production `REDIS_URL` can verify the values take effect immediately, but does **not** persist across a Railway restart — the Start Command override is the only durable fix
- [X] T063 [P] Document the `maxmemory`/`maxmemory-policy` choice — both the `docker-compose.yml` value and the Railway Start Command string from T062a — in `quickstart.md` (or wherever Redis operational config is documented), so a future compose edit or Railway service recreation doesn't silently lose it
- [X] T064 Fix three pre-existing bugs surfaced while verifying T061 against real integration tests (see research.md "Bugs found while verifying the `X-Cache` header against real integration tests"): (1) scope `backend/tests/conftest.py`'s `_no_cache_by_default` autouse fixture to skip unit-test bypass for `@pytest.mark.integration` tests; (2) have it instead bump all four namespaces before each integration test for cross-test isolation, and remove 10 dead `graph_module._cache.clear()` calls in `test_graph.py`; (3) fix `RedisCacheGateway.bump_version()`'s first-bump-is-a-no-op off-by-one via `SETNX` before `INCR`; plus an unrelated `articles_topic_id_fkey` fixture bug in `test_articles.py`'s repeated-request test

**Checkpoint**: Every cache-aside-backed endpoint reports its cache status via `X-Cache`; local dev's `redis` service has a bounded memory footprint that only evicts TTL'd, disposable/tolerable-loss keys, never the durable view-count write-behind buffer or cache version counters. Production is only fully covered once T062a is applied by someone with Railway dashboard access — T054-T064 alone do not change production's Redis config, since `postgres`/`redis` sit outside this repo's deploy pipeline entirely. Full backend suite verified green: 486 unit + 275 integration tests passing.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (US1-US4 all call into `CacheGateway`, and US4's `NotificationHandler` change is independent of caching but is grouped last since it's the lowest-priority story)
- **User Story 1 (Phase 3)**: Depends on Foundational only
- **User Story 2 (Phase 4)**: Depends on Foundational only (does not require US1's implementation, but is more meaningful to test once US1 exists, since US2 verifies that a *previously cached* value gets busted)
- **User Story 3 (Phase 5)**: Depends on Foundational only (same note as US2 — most meaningful once US1 exists)
- **User Story 4 (Phase 6)**: Depends only on Foundational's `REDIS_URL`/skeleton setup being done (T001-T002) — it does NOT depend on `CacheGateway` (T003-T008) at all, since it's pure notification wiring. Can be built fully in parallel with US1/US2/US3 by a separate contributor.
- **Polish (Phase 7)**: Depends on all four user stories being complete

### Parallel Opportunities

- T002 can run in parallel with T001
- T006, T007, T008 can run in parallel once T003-T005 are done
- T012, T013 can run in parallel with T010, T011 (different files)
- T014-T017 can all run in parallel (different test files)
- T019 can run in parallel with T018 (different files)
- T020, T021 can run in parallel
- T025, T026, T027 can run in parallel
- T029-T032 can all run in parallel (four independent new files)
- T037, T038, T039 can run in parallel
- **Whole-story parallelism**: once Phase 2 is done, User Story 4 (Phase 6) can be worked entirely in parallel with User Stories 1-3, since it shares no files with them except `src/bootstrap.py` (different functions within that file: `build_metrics_refresh_pipeline()`/`build_rag_backfill_pipeline()` vs. `build_collection_pipeline()`/`build_weekly_pipeline()`)

---

## Parallel Example: User Story 1

```bash
# Once Foundational (T003-T008) is done, launch US1's four endpoint wrappers together:
Task: "Wrap get_articles_paginated with CacheGateway.get_or_set in backend/services/article_service.py"
Task: "Wrap graph queries with CacheGateway.get_or_set in backend/services/graph_service.py, remove in-process _cache"
Task: "Wrap list_tag_groups/get_tag_group with CacheGateway.get_or_set in backend/routers/tags.py"
Task: "Wrap weekly report reads with CacheGateway.get_or_set in backend/services/weekly_report_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (`CacheGateway`/`RedisCacheGateway`, fully tested)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run quickstart.md §1 and §4 (cache-aside reads + graceful degradation) manually
5. This alone delivers the Web Vitals improvement (spec.md SC-001) — deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → cache infrastructure ready
2. Add User Story 1 → validate → MVP deployable
3. Add User Story 2 → validate admin write-through → deploy
4. Add User Story 3 → validate daily-pipeline write-through → deploy
5. Add User Story 4 → validate CLI notifications → deploy
6. Polish

### Parallel Team Strategy

With multiple developers, after Phase 2 (Foundational) completes:
- Developer A: User Story 1 (the MVP-critical path)
- Developer B: User Stories 2 + 3 (both are write-through invalidation, share context)
- Developer C: User Story 4 (fully independent — no `CacheGateway` dependency at all)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Per this project's standing preference, implementation precedes its tests within each story (not strict TDD) — but every story still ships with dedicated test coverage per Constitution §III
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
