# Feature Specification: Redis Caching Layer for Read APIs

**Feature Branch**: `020-redis-caching-layer`

**Created**: 2026-08-06

**Status**: Draft

**Input**: User description: "在 frontend/app 中改善 Web Vitals 效能指標，做法是為現有直接打 DB 的 read API 加上 Redis caching 層，並在每日排程的 scraper pipeline 完成後（以及 admin 後台寫入時）主動維護快取；同時為 refresh_metrics 與 backfill_rag 兩個 CLI entrypoint 加上完成通知"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster browsing of articles, graph, tags, and weekly reports (Priority: P1)

A visitor browses the article list, the analysis graph, tag filters, or a weekly report. Today every one of these views hits the database directly on every request. The visitor should see these pages load noticeably faster, especially on repeat visits within the same day, because the underlying data barely changes between visits (articles are only refreshed once a day).

**Why this priority**: This is the actual Web Vitals goal driving the feature — it's the only story with direct, measurable end-user impact. Nothing else matters if this doesn't materialize.

**Independent Test**: Load the article list, graph, tag-group list, and weekly report pages twice in a row (with no data changes in between) and confirm the second load returns noticeably faster than the first, without requiring any other story to be implemented.

**Acceptance Scenarios**:

1. **Given** an article list has been viewed once with a given filter/sort/page combination, **When** the same combination is requested again before any underlying data changes, **Then** the response is served without a fresh database query for that combination.
2. **Given** the analysis graph has been viewed once with a given filter combination, **When** the same combination is requested again, **Then** the response is served without a fresh database query, and remains correct (no stale in-process-only cache tied to a single server instance).
3. **Given** the tag-group list or a weekly report has been viewed once, **When** it is requested again, **Then** the response is served without a fresh database query.

---

### User Story 2 - Admin changes are visible immediately (Priority: P2)

An admin edits a topic, tag, or scraper setting from the admin dashboard. Visitors browsing the site should see the effect of that change right away — not have to wait up to a day for the next scheduled pipeline run to refresh stale cached data.

**Why this priority**: Caching is only safe to ship if it doesn't silently make the admin's own changes appear to "not work." This directly protects the admin's trust in the system and prevents confusing support situations.

**Independent Test**: As an admin, edit a topic/tag/scraper setting, then immediately load the affected visitor-facing page and confirm the change is reflected — independent of whether the daily pipeline has run.

**Acceptance Scenarios**:

1. **Given** an admin renames or deletes a tag, **When** a visitor requests the tag-group list right after, **Then** the response reflects the change, not a previously cached value.
2. **Given** an admin edits a topic, **When** a visitor requests article or graph views scoped to that topic right after, **Then** the response reflects the change.

---

### User Story 3 - Freshly scraped content appears without manual intervention (Priority: P3)

Once a day, the scheduled scraper pipeline finishes collecting and analyzing new articles. Visitors should see this new content in the article list, graph, and weekly report views right after the pipeline completes, without an operator needing to manually clear any cache.

**Why this priority**: This is the scheduled-refresh half of cache correctness (the other half is User Story 2's on-demand admin refresh). It's P3 because a same-day TTL safety net (User Story 1) would eventually surface new content anyway even if this story were missing — but without it, freshness could lag by up to the cache's TTL.

**Independent Test**: Trigger a scrape pipeline run that produces new articles, then immediately load the article list, graph, and weekly report views and confirm the new content appears without any manual cache-clearing step.

**Acceptance Scenarios**:

1. **Given** the daily scrape pipeline just finished processing new articles, **When** a visitor requests the article list or graph, **Then** the new articles are reflected in the response.
2. **Given** a new weekly report was just generated, **When** a visitor requests the weekly reports view, **Then** the new report is reflected in the response.

---

### User Story 4 - Operators are notified when metrics-refresh and RAG-backfill jobs finish (Priority: P3)

Operators already get a completion notification when the main scraping pipeline and the weekly report job finish. Two other scheduled jobs — refreshing citation/metric data and backfilling the RAG index — currently finish silently. Operators should get the same kind of completion notification for these two jobs, so they have equal visibility into all scheduled jobs without having to check logs.

**Why this priority**: This is an operational visibility improvement, independent of the caching work, bundled into this feature because it follows the same "job finishes → notify" pattern already used by the pipeline this feature also touches. It doesn't affect end users, hence lower priority than the caching stories.

**Independent Test**: Run the metrics-refresh job and the RAG-backfill job (success and failure cases) and confirm an operator notification is sent for each, matching the existing notification format/channel used by the main pipeline and weekly report job.

**Acceptance Scenarios**:

1. **Given** the metrics-refresh job completes (successfully or with failures), **When** the job finishes, **Then** operators receive a completion notification summarizing the outcome.
2. **Given** the RAG-backfill job completes (successfully or with failures), **When** the job finishes, **Then** operators receive a completion notification summarizing the outcome.

---

### Edge Cases

- What happens when the cache is temporarily unavailable? Visitors must still be able to browse every page covered by this feature — reads fall back to the database rather than failing the request.
- What happens the very first time a given filter/sort/page combination is requested (cache miss, nothing cached yet)? The response is computed from the database and only then cached for subsequent requests.
- What happens if an admin write and a scheduled pipeline write happen to overlap in time? The cached data must end up consistent with the latest completed write — a visitor must never see a permanently stuck stale value because of the overlap.
- What happens if a cache-invalidation signal is somehow missed (e.g., a process crashes mid-write)? Cached data must not persist indefinitely — it must still expire on its own within a bounded time even without an explicit invalidation.
- What happens if sending an operator notification fails (e.g., the notification channel is temporarily down)? The metrics-refresh or RAG-backfill job's own data changes must not be affected or rolled back because of a notification failure.
- What happens to an admin's own next page load immediately after their edit, before any cache has been populated for the new state? It must reflect the new state, not a leftover cached response from before the edit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST serve cached responses for the article list view (with its filter, sort, and pagination options) once a given combination has been requested at least once, instead of always querying the database.
- **FR-002**: System MUST serve cached responses for the analysis graph view (with its filter options), replacing the current per-server, time-limited caching behavior with one that is consistent across all server instances.
- **FR-003**: System MUST serve cached responses for the tag-group list view.
- **FR-004**: System MUST serve cached responses for the weekly reports views (the list, the latest report, a specific week, and the list of available weeks).
- **FR-005**: When the daily scheduled scraping pipeline completes, System MUST make newly collected/analyzed data visible in the views covered by FR-001–FR-004 without waiting for any cached entry to expire on its own.
- **FR-006**: When an admin creates, edits, or deletes a topic, tag, or scraper setting, System MUST make that change visible in the affected views covered by FR-001–FR-004 immediately as part of completing that write — not on a delay.
- **FR-007**: For views with a very large number of possible filter/sort/pagination combinations (the article list), System MUST NOT require every combination to be precomputed ahead of time; combinations may be cached on first use.
- **FR-008**: System MUST bound how long any cached entry can remain stale even if an expected refresh/invalidation is missed, so that staleness cannot persist indefinitely.
- **FR-009**: If cached data is unavailable for a requested view (cache miss, or the caching layer itself is unavailable), System MUST still return a correct response by falling back to the database rather than failing the request.
- **FR-010**: System MUST send operators a completion notification when the metrics-refresh scheduled job finishes, summarizing success/failure, consistent with the notification already sent for the main scraping pipeline and the weekly report job.
- **FR-011**: System MUST send operators a completion notification when the RAG-backfill scheduled job finishes, summarizing success/failure, in the same manner as FR-010.
- **FR-012**: A failure to deliver an operator notification (FR-010, FR-011) MUST NOT cause the triggering job to fail or cause any of that job's already-completed data changes to be rolled back.

### Key Entities

- **Cached View Response**: A stored, reusable result for one specific read view + parameter combination (e.g., one article-list filter/sort/page combination, or one graph filter combination), with a bounded lifetime.
- **Cache Invalidation Signal**: The trigger, originating from either the daily scraping pipeline finishing or an admin write completing, that causes affected Cached View Responses to stop being served and be recomputed on next use.
- **Job Completion Notification**: A message summarizing the outcome (success/failure counts) of a finished scheduled job, sent to operators — an existing concept for the main pipeline and weekly report job, extended in this feature to two additional jobs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Repeat views of the article list, graph, tag list, and weekly report pages (same parameters, no underlying data change) are measurably faster than the very first view of that same combination.
- **SC-002**: 100% of admin changes to topics, tags, and scraper settings are reflected on the very next visitor page view of the affected data — zero instances of a visitor seeing pre-edit data after an admin's edit completes.
- **SC-003**: Newly scraped articles, analyses, and weekly reports become visible to visitors within the views covered by this feature immediately after the daily pipeline finishes, without any manual intervention.
- **SC-004**: Visitors experience zero additional page-load failures attributable to the caching layer — every covered page remains fully browsable even when the caching layer is degraded or unavailable.
- **SC-005**: Operators have equal completion visibility across all four scheduled jobs (main pipeline, weekly report, metrics-refresh, RAG-backfill) — 100% of runs of the latter two now produce a completion notification, matching the other two.

## Assumptions

- Redis, already present in the deployed stack, is the caching technology used; this feature introduces no new infrastructure dependency.
- Caching logic runs within the existing scraper CLI process and the existing backend API process; no new standalone service or message queue is introduced by this feature.
- The daily scraping pipeline and the admin write endpoints (topics, tags, scraper settings) are the only write paths that need to trigger cache freshness for the views in scope; no other write path bypasses them for this data.
- "Operators" and the notification channel/format in FR-010/FR-011 refer to the same audience and mechanism already used for the main scraping pipeline's and weekly report job's completion notifications — no new notification channel is introduced.
- The `translate` and `dedup_reconcile` scheduled jobs are explicitly out of scope for the notification extension (User Story 4) in this feature.
- Frontend-side Web Vitals levers other than API response caching (bundle size, image optimization, etc.) are out of scope for this feature, with one narrow exception carved out post-launch — see the Addendum below.

## Addendum: Frontend Article-Detail Session Cache (2026-08-13)

Added after initial launch, in response to a real usage report: repeatedly opening the same article's detail dialog within one browsing session re-fetched `GET /articles/{id}` every time, even though the article had just been viewed. This is a client-side, in-memory complement to the backend Redis cache above — it does not touch Redis, PostgreSQL, or any backend code, and does not change the freshness guarantees FR-001–FR-009 make about what the *backend* serves.

**Behavior**: The frontend keeps an in-memory LRU cache (capacity 10, keyed by `locale:article_id`) of `GET /articles/{id}` responses, scoped to the current browser tab session (a page reload clears it — no `sessionStorage`/`localStorage` persistence). Re-opening an already-cached article's detail dialog is served from this cache instead of issuing a new request.

**Deliberate scope decision — `view_count`/`metrics` staleness**: Unlike the backend cache (which excludes `view_count`/`metrics` from what it caches specifically so they stay live per-request — see `backend/routers/articles.py`), the frontend cache stores the entire response, including those two fields. Re-opening the same article within one session can therefore show a `view_count`/`metrics` snapshot that's a few minutes stale. This is accepted as out of scope for correctness: the staleness window is bounded to one tab's session, and the two extra DB queries this would otherwise force on every dialog re-open aren't worth paying just to keep a view counter live to the second for a browsing session's own repeat views.

**Implementation**: `frontend/lib/cache/lru-cache.ts` (generic `LRUCache<K, V>`, `Map`-backed — insertion-order iteration gives O(1) recency tracking and eviction without a hand-rolled linked list), wired into `frontend/lib/api/articles.ts::fetchArticleById()`.
