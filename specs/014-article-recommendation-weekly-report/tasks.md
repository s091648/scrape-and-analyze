# Tasks: Article Recommendation Signals & Weekly Summary Report

**Feature**: `014-article-recommendation-weekly-report`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md) | **API**: [contracts/api.md](contracts/api.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependencies and environment configuration needed across all user stories

- [ ] T001 Add `boto3>=1.34` and `resend>=2.0` to `pyproject.toml` core dependencies group
- [ ] T002 Add `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `IMAGEN_API_KEY`, `VIEW_COUNT_FLUSH_INTERVAL` to `.env.example` with comments
- [ ] T003 [P] Add gemini-imagen provider entry (`type='multimodal'`, `model='imagen-3.0-generate-001'`) to `providers.toml`

---

## Phase 2: Foundational (Blocking Prerequisites — DB Migrations & ORM Models)

**Purpose**: Create database tables and ORM models that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create Alembic migration `alembic/versions/18_article_metrics_table.py` per data-model.md `article_metrics` DDL (article_id FK, citation_count nullable, view_count, last_flushed_at, indexes)
- [ ] T005 [P] Create Alembic migration `alembic/versions/19_weekly_reports_table.py` per data-model.md `weekly_reports` DDL (topic_id FK, week_start_date, title, summary_text, cover_image_url, article_ids JSONB, status, UNIQUE on topic_id+week_start_date)
- [ ] T006 [P] Create Alembic migration `alembic/versions/20_user_subscription_tables.py` per data-model.md: `user_topic_subscriptions`, `user_notification_settings`, and `user_article_favorites` tables with all FKs and UNIQUE constraints
- [ ] T007 [P] Create Alembic migration `alembic/versions/21_llm_provider_type_multimodal.py` to update `CheckConstraint` on `llm_providers.type` to allow `'llm'`, `'embedding'`, `'multimodal'`
- [ ] T008 [P] Create ORM model `models/article_metrics.py` with `ArticleMetrics` class (UUID PK, article_id FK → articles, citation_count nullable int, view_count int default 0, last_flushed_at, UNIQUE on article_id)
- [ ] T009 [P] Create ORM model `models/weekly_report.py` with `WeeklyReport` class (UUID PK, topic_id FK → topics ON DELETE SET NULL, week_start_date, title, summary_text, cover_image_url, article_ids JSONB, article_count, status, error_message)
- [ ] T010 [P] Create ORM model `models/user_subscription.py` with three classes: `UserTopicSubscription` (user_id+topic_id UNIQUE), `UserNotificationSettings` (user_id UNIQUE, email_enabled, telegram_chat_id, telegram_enabled), `UserArticleFavorite` (user_id+article_id UNIQUE)
- [ ] T011 [P] Extend `models/llm_provider.py` `CheckConstraint` to include `'multimodal'` in allowed type values alongside `'llm'` and `'embedding'`

**Checkpoint**: All migrations and ORM models complete — user story implementation can begin

---

## Phase 3: User Story 1 — View Article Recommendation Signals (Priority: P1) 🎯 MVP

**Goal**: Show citation_count and view_count on article cards and detail dialog; track views via Redis with IP dedup

**Independent Test**: Visit `/articles`, open an article from OpenAlex or Semantic Scholar — citation count badge appears on card. Click into any article detail dialog — view count is visible and increments via Redis.

### Implementation

- [ ] T012 [P] [US1] Extend `src/modules/collection/domain/value_objects/scraped_article.py` with `citation_count: Optional[int] = None` field
- [ ] T013 [P] [US1] Extend `src/infrastructure/collection/scrapers/openalex_scraper.py` to extract and pass `citation_count` into `ScrapedArticle`
- [ ] T014 [P] [US1] Extend `src/infrastructure/collection/scrapers/semantic_scholar_scraper.py` to extract and pass `citation_count` into `ScrapedArticle`
- [ ] T015 [US1] Extend `ProcessScrapedArticleUseCase` in `src/modules/collection/application/use_cases/process_scraped_article_use_case.py` to upsert `article_metrics` row (citation_count from ScrapedArticle, view_count=0) after article save; depends on T012, T008
- [ ] T016 [P] [US1] Extend `backend/schemas/article.py` `ArticleOut` and `ArticleDetailOut` with `citation_count: Optional[int] = None` and `view_count: int = 0`
- [ ] T017 [US1] Extend `backend/services/article_service.py` `get_articles_paginated` to `LEFT JOIN article_metrics` and include `citation_count`, `view_count` in output mapping; depends on T016, T008
- [ ] T018 [US1] Add `POST /articles/{id}/view` endpoint to `backend/routers/articles.py`: Redis `INCR view:{article_id}` with IP dedup key `viewed:{ip}:{article_id}` (24h TTL via `EXPIRE`); returns 204 regardless of duplicate
- [ ] T019 [US1] Add view count flush function to `backend/services/article_service.py` (scan `view:*` Redis keys, `GETDEL`, `UPDATE article_metrics SET view_count = view_count + :count`); add admin endpoint `POST /admin/articles/flush-view-counts` in `backend/routers/articles.py`; register background periodic flush on FastAPI startup using `VIEW_COUNT_FLUSH_INTERVAL` env var (default 900s)
- [ ] T020 [P] [US1] Extend `frontend/lib/api/articles.ts` with `recordArticleView(id: string)` fire-and-forget function (`POST /articles/{id}/view`); update `ArticleOut` TypeScript type with `citation_count: number | null` and `view_count: number`
- [ ] T021 [US1] Extend `frontend/components/features/articles/article-card.tsx` to show `citation_count` badge (when > 0) and `view_count` badge using the new fields from T020
- [ ] T022 [US1] Extend `frontend/components/features/articles/article-detail-dialog.tsx` to display `citation_count` and `view_count`, and call `recordArticleView(id)` on dialog open; depends on T020

### Tests

- [ ] T023 [P] [US1] Write unit test for `ProcessScrapedArticleUseCase` article_metrics upsert behavior in `src/tests/unit/test_process_scraped_article.py`
- [ ] T024 [P] [US1] Write backend integration test for `POST /articles/{id}/view` endpoint and Redis IP dedup (second call within 24h does not increment) in `backend/tests/test_article_view_count.py`

**Checkpoint**: Citation count and view count visible on article cards and detail dialog; POST /articles/{id}/view increments Redis counter correctly

---

## Phase 4: User Story 2 — Sort Articles by Recommendation Signals (Priority: P2)

**Goal**: Add sort dropdown to filter bar; extend GET /articles to support citation_count and view_count sort

**Independent Test**: Open articles page, select "Sort by: Citation Count" from sort dropdown — articles reorder with highest citation count first. Change topic filter — topic filter is preserved alongside sort.

### Implementation

- [ ] T025 [US2] Extend `backend/services/article_service.py` sort logic in `get_articles_paginated` to handle `sort='citation_count'` and `sort='view_count'` via `ORDER BY` on the `article_metrics` columns from the JOIN established in T017
- [ ] T026 [P] [US2] Extend `frontend/components/features/articles/filter-bar.tsx` with sort `<Select>` dropdown (Shadcn UI) on the right side; options: Scraped At (default), Published At, Citation Count, View Count, Source, Title; immediate apply on change (no draft state)
- [ ] T027 [US2] Update articles page/hook to read `sort` and `order` state and pass as query params to `GET /articles` via `apiFetch()`; depends on T026

### Tests

- [ ] T028 [P] [US2] Write backend integration test for `GET /articles?sort=citation_count&order=desc` correct ordering in `backend/tests/test_article_sort.py`
- [ ] T029 [P] [US2] Write frontend unit test for FilterBar sort dropdown rendering and `onChange` in `frontend/tests/unit/filter-bar.test.tsx`

**Checkpoint**: Sort dropdown visible in filter bar; articles correctly reorder by citation_count and view_count without breaking topic filter

---

## Phase 5: User Story 5 — Favorite an Article (Priority: P2)

**Goal**: Heart icon on article cards toggles favorites; Favorites filter restricts article list; backend favorites API

**Independent Test**: Log in, click heart icon on article card — icon fills, `user_article_favorites` DB row created. Enable Favorites filter — only favorited articles shown. Click filled heart again — icon empties, DB row deleted.

### Implementation

- [ ] T030 [P] [US5] Extend `backend/schemas/article.py` `ArticleOut` with `is_favorited: bool = False`
- [ ] T031 [US5] Extend `backend/services/article_service.py` to `LEFT JOIN user_article_favorites` for authenticated users to populate `is_favorited`; add `favorites_only: bool = False` query param that restricts results to user's favorited articles; depends on T030, T010
- [ ] T032 [US5] Create `backend/routers/user.py` with `GET /user/favorites` (returns `{"article_ids": [...]}` list), `POST /user/favorites/{article_id}` (`INSERT … ON CONFLICT DO NOTHING`, 201 or 204), `DELETE /user/favorites/{article_id}` (204) — all with `require_user` auth
- [ ] T033 [US5] Register `backend/routers/user.py` router in `backend/main.py`
- [ ] T034 [P] [US5] Add `addFavorite(articleId: string)`, `removeFavorite(articleId: string)`, `getFavorites()` functions to `frontend/lib/api/user.ts`
- [ ] T035 [US5] Extend `frontend/lib/api/articles.ts` `ArticleOut` TypeScript type with `is_favorited: boolean`; update article fetch function to accept and pass `favorites_only` query param; depends on T030
- [ ] T036 [US5] Extend `frontend/components/features/articles/article-card.tsx` with heart icon left of title: hover-visible when unfavorited, always-visible when favorited, hidden for unauthenticated guests; click calls `addFavorite`/`removeFavorite` and toggles local state; depends on T034, T035
- [ ] T037 [US5] Extend `frontend/components/features/articles/filter-bar.tsx` with Favorites toggle button (visible for authenticated users only); activating passes `favorites_only=true` to articles API; depends on T034

### Tests

- [ ] T038 [P] [US5] Write backend integration test for `POST/DELETE/GET /user/favorites` endpoints including idempotency in `backend/tests/test_user_favorites.py`
- [ ] T039 [P] [US5] Write backend integration test for `GET /articles?favorites_only=true` restricting results to authenticated user's favorited articles in `backend/tests/test_article_favorites_filter.py`

**Checkpoint**: Heart icon toggles favorites; Favorites filter shows only user's articles; all favorites endpoints return correct responses

---

## Phase 6: User Story 3 — Subscribe to Topic for Weekly Report (Priority: P3)

**Goal**: Build weekly report generation infrastructure (LLM, image gen, R2 storage, notifications) and subscription management API + settings UI

**Independent Test**: Visit settings page, subscribe to a topic — `user_topic_subscriptions` DB row created. Trigger weekly report generation via admin API — report generated, subscribed users receive email (if email_enabled) and Telegram (if telegram_chat_id set) notifications.

### Implementation — DDD Domain Layer

- [ ] T040 [P] [US3] Create `src/modules/weekly_report/domain/entities/weekly_report.py` with `WeeklyReport` dataclass (id, topic_id, week_start_date, title, summary_text, cover_image_url, article_ids, article_count, status, error_message)
- [ ] T041 [P] [US3] Create `src/modules/weekly_report/domain/repositories/weekly_report_repository.py` abstract repository interface (fetch top articles by topic/week using sort strategy from data-model.md, get/save WeeklyReport)
- [ ] T042 [P] [US3] Create `src/modules/weekly_report/domain/services/image_generation_service.py` abstract service interface (`generate_image(prompt: str) -> bytes`)
- [ ] T043 [P] [US3] Create `src/modules/weekly_report/domain/services/blob_storage_service.py` abstract interface (`upload(data: bytes, key: str, content_type: str) -> str` returns public URL); use case injects this interface, not `R2BlobStorageService` directly
- [ ] T044 [P] [US3] Create `src/modules/weekly_report/domain/value_objects/article_summary_for_report.py` frozen dataclass: `title`, `summary`, `pain_points`, `insights`, `innovations` (all Optional[str] from analyses table), `tags: List[str]` (flat tag list), `citation_count: Optional[int]`, `view_count: int`, `published_at: Optional[datetime]`
- [ ] T045 [P] [US3] Create `src/modules/weekly_report/domain/value_objects/weekly_report_prompt.py` extending `BasePrompt`; `render(topic_name: str, articles: List[ArticleSummaryForReport], week_start: date)` fills template and returns JSON-requesting prompt for `{"title": "...", "summary_text": "..."}` output
- [ ] T046 [P] [US3] Create `src/modules/weekly_report/domain/value_objects/image_generation_prompt.py` extending `BasePrompt`; `render(topic_name: str, top_tags: List[str], week_label: str)` returns image generation prompt string (16:9 abstract art, futuristic data visualization aesthetic)

### Implementation — Application Layer

- [ ] T047 [US3] Create `src/modules/weekly_report/application/use_cases/generate_weekly_report_use_case.py` orchestrating: (1) fetch top N articles via repo (COALESCE sort), (2) derive `top_tags` by frequency count, (3) `WeeklyReportPrompt().render(...)` → `LLMService.analyze()` → parse JSON title+summary, (4) `ImageGenerationPrompt().render(...)` → `ImageGenerationService.generate_image()` → `BlobStorageService.upload()`, (5) persist WeeklyReport, (6) send email+Telegram to subscribed users; depends on T040–T046

### Implementation — Infrastructure Layer

- [ ] T048 [P] [US3] Create `src/infrastructure/intelligence/image/base_image_provider.py` abstract base class for image generation providers
- [ ] T049 [P] [US3] Create `src/infrastructure/intelligence/image/gemini_imagen_provider.py` implementing `ImageGenerationService` using `google-genai` SDK and `imagen-3.0-generate-001` model; depends on T042, T048
- [ ] T050 [P] [US3] Create `src/infrastructure/storage/r2_blob_storage.py` `R2BlobStorageService` implementing `BlobStorageService` (T043) using `boto3` S3-compatible client with `R2_*` env vars; depends on T043
- [ ] T051 [US3] Create `src/infrastructure/weekly_report/repositories/weekly_report_repo_impl.py` `WeeklyReportRepoImpl` implementing repository interface (T041): fetches articles+analyses+tags via JOIN with `COALESCE(citation_count,0) DESC, view_count DESC, published_at DESC NULLS LAST`, assembles `ArticleSummaryForReport` list, upserts `WeeklyReport` ORM row; depends on T041, T044

### Implementation — Notifications

- [ ] T052 [P] [US3] Create `src/infrastructure/notifications/weekly_report_email_notifier.py` `WeeklyReportEmailNotifier` using `resend` Python SDK; queries `user_notification_settings` for subscribed users with `email_enabled=True`; sends HTML email per user using `RESEND_API_KEY` and `RESEND_FROM_EMAIL`
- [ ] T053 [P] [US3] Create `src/infrastructure/notifications/weekly_report_telegram_notifier.py` `WeeklyReportTelegramNotifier` reusing existing Telegram HTTP pattern; queries `user_notification_settings` for subscribed users with `telegram_enabled=True` and non-null `telegram_chat_id`; sends per-user message

### Implementation — Bootstrap & Entrypoint

- [ ] T054 [US3] Add `build_weekly_pipeline()` to `src/bootstrap.py` wiring: `WeeklyReportRepoImpl`, `ResilientLLMService` (reuse existing builder), `GeminiImagenProvider`, `R2BlobStorageService`, `WeeklyReportEmailNotifier`, `WeeklyReportTelegramNotifier` → `GenerateWeeklyReportUseCase`; depends on T047–T053
- [ ] T055 [US3] Create `src/entrypoints/cli/weekly_main.py` CLI entrypoint calling `build_weekly_pipeline()` and running `GenerateWeeklyReportUseCase` for each active topic with articles in the past 7 days; accepts `--topic-id` and `--week-start` CLI args for manual triggers; depends on T054

### Implementation — Backend Subscription & Notification Settings API

- [ ] T056 [P] [US3] Add `GET /user/subscriptions`, `POST /user/subscriptions` (`{"topic_id": "uuid"}`), `DELETE /user/subscriptions/{topic_id}` endpoints to `backend/routers/user.py` (require_user auth)
- [ ] T057 [P] [US3] Add `GET /user/notification-settings`, `PUT /user/notification-settings` endpoints to `backend/routers/user.py` (require_user auth, upsert pattern on `UserNotificationSettings`)

### Implementation — Frontend Settings UI

- [ ] T058 [P] [US3] Extend `frontend/app/settings/page.tsx` with topic subscription section: list all topics, Subscribe/Unsubscribe buttons per topic, reads current subscriptions via `fetchSubscriptions()`
- [ ] T059 [P] [US3] Extend `frontend/app/settings/page.tsx` with notification settings form: email_enabled toggle, telegram_chat_id text input, telegram_enabled toggle; calls `fetchNotificationSettings()` on load and `updateNotificationSettings()` on save
- [ ] T060 [P] [US3] Add `fetchSubscriptions()`, `subscribeToTopic(topicId)`, `unsubscribeTopic(topicId)`, `fetchNotificationSettings()`, `updateNotificationSettings(settings)` to `frontend/lib/api/user.ts`

### Tests

- [ ] T061 [P] [US3] Write unit test for `GenerateWeeklyReportUseCase` (mock LLM service, image gen, blob storage, notifiers) in `src/tests/unit/test_generate_weekly_report_use_case.py`
- [ ] T062 [P] [US3] Write unit test for `GeminiImagenProvider` (mock google-genai client) in `src/tests/unit/test_gemini_imagen_provider.py`
- [ ] T063 [P] [US3] Write unit test for `R2BlobStorageService` (mock boto3 client, verify upload URL construction) in `src/tests/unit/test_r2_blob_storage.py`
- [ ] T064 [P] [US3] Write backend integration test for `GET/POST/DELETE /user/subscriptions` and `GET/PUT /user/notification-settings` in `backend/tests/test_user_subscriptions.py`

**Checkpoint**: Weekly report generation runs end-to-end (may use mocked R2/Imagen); subscribed users receive notifications; settings page allows subscription and notification management

---

## Phase 7: User Story 4 — View Weekly Summary Report on Homepage (Priority: P4)

**Goal**: Display latest weekly report above InlineQABar on homepage with cover image; dropdown to navigate past reports

**Independent Test**: Trigger weekly report generation via admin API, visit `/` — report appears above InlineQABar with cover image (or text-only if R2 unavailable). Open week dropdown — can navigate to past weekly reports.

### Implementation — Backend

- [ ] T065 [P] [US4] Create `backend/schemas/weekly_report.py` with `WeeklyReportOut` Pydantic schema (id, topic_id, week_start_date, title, summary_text, cover_image_url, article_count, status, created_at)
- [ ] T066 [P] [US4] Create `backend/services/weekly_report_service.py` with `get_weekly_reports(topic_id, limit, offset)` and `get_latest_weekly_report(topic_id)` (returns most recent `status='completed'` report) functions
- [ ] T067 [US4] Create `backend/routers/weekly_reports.py` with `GET /weekly-reports` (paginated, public), `GET /weekly-reports/latest` (single, public), `POST /admin/weekly-reports/generate` (require_admin, body: topic_id + week_start_date); depends on T065, T066
- [ ] T068 [US4] Register `backend/routers/weekly_reports.py` in `backend/main.py`; depends on T067

### Implementation — Frontend

- [ ] T069 [P] [US4] Create `frontend/lib/api/weekly-reports.ts` with `fetchLatestWeeklyReport(topicId: string)` and `fetchWeeklyReports(topicId: string, limit?: number, offset?: number)` using `apiFetch()`
- [ ] T070 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-skeleton.tsx` loading skeleton component
- [ ] T071 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-card.tsx` displaying report title, summary_text (markdown rendered), and cover_image_url as CSS background-image
- [ ] T072 [US4] Create `frontend/components/features/weekly-report/weekly-report-widget.tsx` with week navigation dropdown (Shadcn Select) and `WeeklyReportCard`; fetches via `fetchLatestWeeklyReport`/`fetchWeeklyReports`; shows "No report for this week yet" placeholder when null; uses `WeeklyReportSkeleton` while loading; depends on T069, T070, T071
- [ ] T073 [US4] Extend `frontend/app/page.tsx` to render `<WeeklyReportWidget topicId={currentTopicId} />` above `<InlineQABarWrapper>`; depends on T072
- [ ] T074 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-widget.stories.tsx` Storybook story (required by Constitution §II) with no-report and with-report states
- [ ] T075 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-card.stories.tsx` Storybook story (required by Constitution §II) with and without cover image

### Tests

- [ ] T076 [P] [US4] Write backend integration test for `GET /weekly-reports` and `GET /weekly-reports/latest` in `backend/tests/test_weekly_reports.py`
- [ ] T077 [P] [US4] Write frontend unit test for `WeeklyReportWidget` (empty state, loaded state) in `frontend/tests/unit/weekly-report-widget.test.tsx`

**Checkpoint**: Homepage displays weekly report widget above InlineQABar; empty state shows placeholder; week dropdown navigates past reports

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation and final cross-cutting quality checks

- [ ] T078 [P] Write E2E test for sort by citation_count reordering the article list in `frontend/tests/integration/sort-articles.spec.ts`
- [ ] T079 [P] Write E2E test for weekly report widget display and week dropdown navigation in `frontend/tests/integration/weekly-report-widget.spec.ts`
- [ ] T080 Run quickstart.md validation: apply migrations 18–21 via `docker compose run --rm job_service make migrate`, generate a weekly report via admin API, verify citation count on scraped articles, and verify view count tracking and flush

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1; BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (needs `ArticleMetrics` ORM T008)
- **US2 (Phase 4)**: Depends on Phase 3 (needs `article_metrics` JOIN from T017)
- **US5 (Phase 5)**: Depends on Phase 2 (needs `UserArticleFavorite` ORM T010); can start in parallel with Phase 3/4
- **US3 (Phase 6)**: Depends on Phase 2 (needs `WeeklyReport`, `UserTopicSubscription`, `UserNotificationSettings` ORMs T009, T010); largely independent of Phase 3–5
- **US4 (Phase 7)**: Depends on Phase 6 (weekly reports must be generable for meaningful testing)
- **Polish (Phase 8)**: Depends on all user story phases

### User Story Dependencies

| Story | Depends On | Notes |
|-------|------------|-------|
| US1 (P1) | Phase 2 complete | No story-level dependencies |
| US2 (P2) | US1 T017 | Extends existing `article_metrics` JOIN |
| US5 (P2) | Phase 2 complete | Shares `filter-bar.tsx` with US2; order: US2 → US5 |
| US3 (P3) | Phase 2 complete | New DDD bounded context, largely independent |
| US4 (P4) | US3 complete | Needs weekly reports to exist in DB |

### Within Each User Story

- Domain entities before services/value objects before repositories
- Backend schemas before services before routers
- Backend implementation before frontend API client
- Frontend API client before frontend components
- Implementation before tests (no TDD per project preference)

---

## Parallel Opportunities

### Phase 2 (after T004 sets revision chain)

T005–T011 can all run in parallel.

### Phase 3 (US1)

T012, T013, T014 (ScrapedArticle + scraper extensions) run in parallel.
T016, T020 (backend schema + frontend type) run in parallel.
T023, T024 (tests) run in parallel after implementation.

### Phase 6 (US3)

T040–T046 (domain layer) run in parallel — entities, interfaces, value objects all have no inter-dependencies.
T048, T049, T050, T052, T053 (infrastructure) run in parallel after T042/T043.
T056, T057, T058, T059, T060 (backend API + frontend settings) run in parallel.
T061, T062, T063, T064 (tests) run in parallel.

### Parallel Example: Phase 6 Domain Layer

```bash
# All domain tasks in parallel:
Task T040: Create weekly_report.py entity
Task T041: Create weekly_report_repository.py interface
Task T042: Create image_generation_service.py interface
Task T043: Create blob_storage_service.py interface
Task T044: Create article_summary_for_report.py DTO
Task T045: Create weekly_report_prompt.py value object
Task T046: Create image_generation_prompt.py value object
# Then T047 (use case) which depends on all of T040-T046
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational migrations and ORM models
3. Complete Phase 3: US1 — citation count display + view tracking
4. **STOP and VALIDATE**: Scrape an OpenAlex article and verify citation count badge appears on card
5. Deploy if ready

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → Citation counts and view tracking live (MVP)
3. Phase 4 (US2) → Sort by recommendation signals available
4. Phase 5 (US5) → Favorites feature live
5. Phase 6 (US3) → Weekly report generation + subscriptions + notifications live
6. Phase 7 (US4) → Homepage weekly report widget live
7. Phase 8 → E2E tests and final validation

### Parallel Team Strategy

After Phase 2 completes:
- **Developer A**: US1 (Phase 3) → US2 (Phase 4)
- **Developer B**: US5 (Phase 5) in parallel
- **Developer C**: US3 (Phase 6) DDD infrastructure + entrypoint
- US4 (Phase 7) starts after US3 completes

---

## Notes

- `[P]` tasks = different files, no blocking dependencies — safe to run in parallel
- `[Story]` label maps task to specific user story for traceability
- Favorites (`backend/routers/user.py` created in Phase 5) and Subscriptions (endpoints added in Phase 6) share the same router file — Phase 5 creates it, Phase 6 extends it
- Migrations 18–21 are additive (new tables) except 21 which modifies a CheckConstraint — all run via `make migrate`
- Constitution §II requires Storybook stories for all new feature components (T074, T075)
- Weekly runner entrypoint (T055) deploys as Railway Cron Service: `0 8 * * 1`
- `WeeklyReportPrompt` and `ImageGenerationPrompt` live in `weekly_report/domain/value_objects/`, NOT in `intelligence/domain/value_objects/` — different bounded context
- `BlobStorageService` interface (T043) ensures the use case (T047) depends only on domain abstractions, not on R2 directly — required for hexagonal architecture compliance
