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

- [X] T001 Add `boto3>=1.34` and `resend>=2.0` to `pyproject.toml` core dependencies group (`google-genai` already present)
- [X] T002 Add `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `VIEW_COUNT_FLUSH_INTERVAL` to `.env.example` with comments
- [X] T003 Add `jmespath>=1.0` to `pyproject.toml` `scraper` dependency group (research.md §9c)

---

## Phase 2: Foundational (Blocking Prerequisites — DB Migrations & ORM Models)

**Purpose**: Create database tables and ORM models that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 **REWORK (2026-07-12)** Edit Alembic migration `alembic/versions/23_article_recommendation_weekly_report.py` (revises `22_add_correlation_id_and_rag_providers`, still unshipped — edit in place, do not add a follow-up revision): remove `citation_count` column from the `article_metrics` table def + drop its old index; add `metric_definitions` table (id, metric_key, provider_name, priority, extractor_type, extractor_spec JSONB, enabled, label_i18n_key, format_hint, unit, timestamps; UNIQUE(metric_key, provider_name); partial index on metric_key WHERE enabled) with seed-data `INSERT` for `citation_count`/`openalex` (priority 1) and `citation_count`/`semantic_scholar` (priority 2) per data-model.md; add `article_metric_values` table (id, article_id FK CASCADE, metric_key, value NUMERIC, last_flushed_at, timestamps; UNIQUE(article_id, metric_key); index on (metric_key, value DESC NULLS LAST); index on last_flushed_at WHERE NOT NULL); add two partial expression indexes on `articles`: `((metadata->>'doi'))` and `((metadata->>'arxiv_id'))`, both `WHERE ... IS NOT NULL`; keep `weekly_reports`/`user_topic_subscriptions`/`user_notification_settings`/`user_article_favorites`/`llm_providers.type` DDL unchanged; update `downgrade()` to match
- [X] T005 [P] **REWORK (2026-07-12)** Edit ORM model `models/article_metrics.py`: remove `citation_count` column, keep `id`, `article_id` FK, `view_count` int default 0, `last_flushed_at`, UNIQUE on article_id
- [X] T006 [P] Create ORM model `models/weekly_report.py` with `WeeklyReport` class (UUID PK, topic_id FK → topics ON DELETE SET NULL, week_start_date, title, summary_text, cover_image_url, article_ids JSONB, article_count, status, error_message)
- [X] T007 [P] Create ORM model `models/user_subscription.py` with three classes: `UserTopicSubscription` (user_id+topic_id UNIQUE), `UserNotificationSettings` (user_id UNIQUE, email_enabled, telegram_chat_id, telegram_enabled, locale String(10) default='en'), `UserArticleFavorite` (user_id+article_id UNIQUE)
- [X] T008 [P] Fix `models/llm_provider.py`: remove duplicate `type` column definition (lines 16–17 currently have two identical `type =` assignments); add `CheckConstraint("type IN ('llm', 'embedding', 'multimodal')", name='ck_llm_provider_type')` to `__table_args__`
- [X] T009 [P] Create ORM model `models/metric_definition.py` with `MetricDefinition` class per data-model.md `metric_definitions` table (id, metric_key, provider_name, priority, extractor_type, extractor_spec JSONB, enabled, label_i18n_key, format_hint, unit, timestamps, UNIQUE(metric_key, provider_name))
- [X] T010 [P] Create ORM model `models/article_metric_value.py` with `ArticleMetricValue` class per data-model.md `article_metric_values` table (id, article_id FK CASCADE, metric_key, value Numeric nullable, last_flushed_at, timestamps, UNIQUE(article_id, metric_key))
- [X] T011 [P] Create `shared/metric_definition.py::load_enabled_metric_definitions(session) -> List[Dict[str, Any]]`, mirroring `shared/llm_provider.py::load_active_providers` (returns metric_key/provider_name/priority/extractor_type/extractor_spec grouped for `ResilientMetricsService` to consume), `enabled=True` rows only, ordered by `(metric_key, priority)`

**Checkpoint**: Migration and ORM models complete — user story implementation can begin

---

## Phase 3: User Story 1 — View Article Recommendation Signals (Priority: P1) 🎯 MVP

**Goal**: Show citation_count and view_count on article cards and detail dialog; track views via Redis with IP dedup

**Independent Test**: Visit `/articles`, open an article from OpenAlex or Semantic Scholar — citation count badge appears on card. Click into any article detail dialog — view count is visible and increments via Redis.

### Implementation

- [X] T012 [P] [US1] **REWORK (2026-07-12)** Edit `src/modules/collection/domain/value_objects/scraped_article.py`: replace `citation_count: Optional[int] = None` field with `metric_seeds: Dict[str, Any] = field(default_factory=dict)`
- [X] T013 [P] [US1] **REWORK (2026-07-12)** Edit `src/infrastructure/collection/scrapers/openalex_scraper.py` to populate `metric_seeds={"citation_count": e.citation_count}` instead of setting the old dedicated field
- [X] T014 [P] [US1] **REWORK (2026-07-12)** Edit `src/infrastructure/collection/scrapers/semantic_scholar_scraper.py` to populate `metric_seeds={"citation_count": e.citation_count}` instead of setting the old dedicated field
- [X] T015 [US1] **REWORK (2026-07-12)** Edit `src/modules/collection/domain/repositories/article_metrics_repository.py`: change `upsert(self, article_id: UUID, citation_count: Optional[int]) -> None` to `upsert(self, article_id: UUID, metrics: dict[str, Any]) -> None`; edit `src/infrastructure/persistence/collection/article_metrics_repo_impl.py`'s `SqlAlchemyArticleMetricsRepository` to write one row per key into `article_metric_values` via `INSERT ... ON CONFLICT (article_id, metric_key) DO UPDATE SET value = EXCLUDED.value, last_flushed_at = now()` instead of updating the old `citation_count` column; edit `ProcessScrapedArticleUseCase` (`src/modules/collection/application/use_cases/process_scraped_article.py`) to forward `ScrapedArticle.metric_seeds` (filtered to known `metric_definitions.metric_key` values) to the generalized `upsert()`; depends on T012, T010, T011
- [X] T016 [P] [US1] Extend `backend/schemas/article.py` `ArticleOut` and `ArticleDetailOut` with `citation_count: Optional[int] = None` and `view_count: int = 0` — **unaffected by 2026-07-12 rework**: response field shape is unchanged, only the backend query sourcing it changes (see T017)
- [X] T017 [US1] **REWORK (2026-07-12)** Edit `backend/services/article_service.py` `get_articles_paginated`: keep `LEFT JOIN article_metrics` for `view_count`; add `LEFT JOIN article_metric_values ON article_metric_values.article_id = articles.id AND article_metric_values.metric_key = 'citation_count'` for `citation_count` (replaces the old direct column reference); depends on T016, T005, T010
- [X] T018 [US1] Add `POST /articles/{id}/view` endpoint to `backend/routers/articles.py`: Redis `INCR view:{article_id}` with IP dedup key `viewed:{ip}:{article_id}` (24h TTL via `EXPIRE`); returns 204 regardless of duplicate
- [X] T019 [US1] Add view count flush function to `backend/services/article_service.py` (scan `view:*` Redis keys, `GETDEL`, `UPDATE article_metrics SET view_count = view_count + :count`); add admin endpoint `POST /admin/articles/flush-view-counts` in `backend/routers/articles.py`; register background periodic flush on FastAPI startup using `VIEW_COUNT_FLUSH_INTERVAL` env var (default 900s) — **unaffected by 2026-07-12 rework**: entirely separate from citation_count/metric_definitions per research.md §9b
- [X] T020 [P] [US1] Extend `frontend/lib/api/articles.ts` with `recordArticleView(id: string)` fire-and-forget function (`POST /articles/{id}/view`); update `ArticleOut` TypeScript type with `citation_count: number | null` and `view_count: number`
- [X] T021 [US1] Extend `frontend/components/features/articles/article-card.tsx` to show `citation_count` badge (when > 0) and `view_count` badge using the new fields from T020
- [X] T022 [US1] Extend `frontend/components/features/articles/article-detail-dialog.tsx` to display `citation_count` and `view_count`, and call `recordArticleView(id)` on dialog open; depends on T020

### Recurring Metric Refresh (new, 2026-07-12 — extends US1: keeps citation_count fresh after the initial scrape)

- [X] T081 [P] [US1] Add `fetch_by_doi(doi: str) -> Optional[dict]` to `src/infrastructure/collection/clients/openalex_client.py`, returning the raw parsed JSON dict (not `OpenAlexEntry`) for a single paper lookup; `fetch_papers()` unchanged
- [X] T082 [P] [US1] Add `fetch_by_doi(doi: str) -> Optional[dict]` to `src/infrastructure/collection/clients/semantic_scholar_client.py`, same contract as T081
- [X] T083 [P] [US1] Create `src/modules/collection/domain/services/metric_extractor.py` — `MetricExtractor` ABC with `fetch(article_identifiers: dict[str, str]) -> Optional[dict]` and `extract(raw_response: dict, extractor_spec: dict) -> Optional[Any]`
- [X] T084 [P] [US1] Create `src/infrastructure/collection/metrics/json_path_extractor.py` — `JsonPathMetricExtractor` implementing `MetricExtractor.extract()` via `jmespath.search(extractor_spec["path"], raw_response)`; `fetch()` delegates to a `provider_name`-keyed dict of fetcher callables (T081, T082); depends on T081, T082, T083, T003
- [X] T085 [US1] Create `src/infrastructure/collection/metrics/resilient_metrics_service.py` — `ResilientMetricsService`, built from `load_enabled_metric_definitions()` (T011) grouped by `metric_key` ordered by `priority`; `fetch_all(article_identifiers: dict) -> dict[str, Any]` walks each metric_key's provider list in order, keeps first non-null result; depends on T011, T084
- [X] T086 [US1] Add `build_metrics_refresh_pipeline()` to `src/bootstrap.py` wiring `ResilientMetricsService` + the generalized `ArticleMetricsRepository`; depends on T085, T015
- [X] T087 [US1] Create `src/entrypoints/cli/refresh_metrics.py`: query articles (via the `articles.metadata` doi/arxiv_id expression indexes from T004) with a missing or stale (`last_flushed_at < now() - interval '1 day'`) `article_metric_values` row for any enabled `metric_key`; resolve `{"doi": ..., "arxiv_id": ...}` per article from `Article.metadata`; call `ResilientMetricsService.fetch_all()`; upsert results via `ArticleMetricsRepository.upsert()`; depends on T086
- [X] T088 Add Railway Cron Service entry for `refresh_metrics.py` in `src/railway.toml` (daily, `0 3 * * *`), reusing `src/Dockerfile`; depends on T087

### Tests

- [X] T023 [P] [US1] **REWORK (2026-07-12)** Update unit test for `ProcessScrapedArticleUseCase` in `src/tests/unit/test_process_scraped_article.py` to cover the generalized `upsert(article_id, metrics: dict)` call (multiple metric_seeds keys, filtered against known metric_definitions)
- [X] T024 [P] [US1] Write backend integration test for `POST /articles/{id}/view` endpoint and Redis IP dedup (second call within 24h does not increment) in `backend/tests/test_article_view_count.py`
- [X] T089 [P] [US1] Write unit test for `JsonPathMetricExtractor.extract()` against fixture OpenAlex/Semantic Scholar JSON responses in `src/tests/unit/test_json_path_metric_extractor.py`
- [X] T090 [P] [US1] Write unit test for `ResilientMetricsService.fetch_all()` fallback ordering (first provider fails/returns null → falls back to next by priority) in `src/tests/unit/test_resilient_metrics_service.py`
- [X] T091 [P] [US1] Write unit test for the generalized `SqlAlchemyArticleMetricsRepository.upsert()` (multiple metric_key rows, ON CONFLICT update) in `src/tests/unit/test_article_metrics_repo.py`
- [X] T092 [P] [US1] Write unit test for `refresh_metrics.py`'s staleness query (missing row vs stale `last_flushed_at` vs fresh row correctly included/excluded) in `src/tests/unit/test_refresh_metrics.py`

**Checkpoint**: Citation count and view count visible on article cards and detail dialog; POST /articles/{id}/view increments Redis counter correctly; `refresh_metrics.py` keeps citation_count fresh independent of scrape time

---

## Phase 4: User Story 2 — Sort Articles by Recommendation Signals (Priority: P2)

**Goal**: Add sort dropdown to filter bar; extend GET /articles to support citation_count and view_count sort

**Independent Test**: Open articles page, select "Sort by: Citation Count" from sort dropdown — articles reorder with highest citation count first. Change topic filter — topic filter is preserved alongside sort.

### Implementation

- [X] T025 [US2] **REWORK (2026-07-12)** Edit `backend/services/article_service.py` sort logic in `get_articles_paginated`: `sort='view_count'` still orders on `article_metrics.view_count`; `sort='citation_count'` now orders on the `article_metric_values.value` column from the T017 JOIN (filtered to `metric_key='citation_count'`), using the new `idx_article_metric_values_metric_key_value` index
- [X] T026 [P] [US2] Extend `frontend/components/features/articles/filter-bar.tsx` with sort `<Select>` dropdown (Shadcn UI) on the right side; options: Scraped At (default), Published At, Citation Count, View Count, Source, Title; immediate apply on change (no draft state)
- [X] T027 [US2] Update articles page/hook to read `sort` and `order` state and pass as query params to `GET /articles` via `apiFetch()`; depends on T026

### Tests

- [X] T028 [P] [US2] **RE-VERIFY (2026-07-12)** Re-run backend integration test for `GET /articles?sort=citation_count&order=desc` in `backend/tests/test_article_sort.py` against the reworked T025 query (fixture data now needs an `article_metric_values` row instead of a flat `article_metrics.citation_count` column); assertions on response ordering are unchanged
- [X] T029 [P] [US2] Write frontend unit test for FilterBar sort dropdown rendering and `onChange` in `frontend/tests/unit/filter-bar.test.tsx`

**Checkpoint**: Sort dropdown visible in filter bar; articles correctly reorder by citation_count and view_count without breaking topic filter

---

## Phase 5: User Story 5 — Favorite an Article (Priority: P2)

**Goal**: Heart icon on article cards toggles favorites; Favorites filter restricts article list; backend favorites API

**Independent Test**: Log in, click heart icon on article card — icon fills, `user_article_favorites` DB row created. Enable Favorites filter — only favorited articles shown. Click filled heart again — icon empties, DB row deleted.

### Implementation

- [X] T030 [P] [US5] Extend `backend/schemas/article.py` `ArticleOut` with `is_favorited: bool = False`
- [X] T031 [US5] Extend `backend/services/article_service.py` to `LEFT JOIN user_article_favorites` for authenticated users to populate `is_favorited`; add `favorites_only: bool = False` query param that restricts results to user's favorited articles; depends on T030, T007
- [X] T032 [US5] Create `backend/routers/user.py` with `GET /user/favorites` (returns `{"article_ids": [...]}` list), `POST /user/favorites/{article_id}` (`INSERT … ON CONFLICT DO NOTHING`, 201 or 204), `DELETE /user/favorites/{article_id}` (204) — all with `require_user` auth
- [X] T033 [US5] Register `backend/routers/user.py` router in `backend/main.py`
- [X] T034 [P] [US5] Add `addFavorite(articleId: string)`, `removeFavorite(articleId: string)`, `getFavorites()` functions to `frontend/lib/api/user.ts`
- [X] T035 [US5] Extend `frontend/lib/api/articles.ts` `ArticleOut` TypeScript type with `is_favorited: boolean`; update article fetch function to accept and pass `favorites_only` query param; depends on T030
- [X] T036 [US5] Extend `frontend/components/features/articles/article-card.tsx` with heart icon left of title: hover-visible when unfavorited, always-visible when favorited, hidden for unauthenticated guests; click calls `addFavorite`/`removeFavorite` and toggles local state; depends on T034, T035
- [X] T037 [US5] Extend `frontend/components/features/articles/filter-bar.tsx` with Favorites toggle button (visible for authenticated users only); activating passes `favorites_only=true` to articles API; depends on T034

### Tests

- [X] T038 [P] [US5] Write backend integration test for `POST/DELETE/GET /user/favorites` endpoints including idempotency in `backend/tests/test_user_favorites.py`
- [X] T039 [P] [US5] Write backend integration test for `GET /articles?favorites_only=true` restricting results to authenticated user's favorited articles in `backend/tests/test_article_favorites_filter.py`

**Checkpoint**: Heart icon toggles favorites; Favorites filter shows only user's articles; all favorites endpoints return correct responses

---

## Phase 6: User Story 3 — Subscribe to Topic for Weekly Report (Priority: P3)

**Goal**: Build weekly report generation infrastructure (LLM, image gen, R2 storage, notifications) and subscription management API + settings UI

**Independent Test**: Visit settings page, subscribe to a topic — `user_topic_subscriptions` DB row created. Trigger weekly report generation via admin API — report generated, subscribed users receive email (if email_enabled) and Telegram (if telegram_chat_id set) notifications.

### Implementation — DDD Domain Layer

- [X] T040 [P] [US3] Create `src/modules/intelligence/domain/entities/weekly_report.py` with `WeeklyReport` dataclass (id, topic_id, week_start_date, title, summary_text, cover_image_url, article_ids, article_count, status, error_message)
- [X] T041 [P] [US3] Create `src/modules/intelligence/domain/repositories/weekly_report_repository.py` abstract repository interface (fetch top articles by topic/week using sort strategy from data-model.md, get/save WeeklyReport)
- [X] T042 [P] [US3] Create `src/modules/intelligence/domain/services/image_generation_service.py` abstract service interface (`generate_image(prompt: str) -> bytes`)
- [X] T043 [P] [US3] Create `src/modules/intelligence/domain/services/blob_storage_service.py` abstract interface (`upload(data: bytes, key: str, content_type: str) -> str` returns public URL); use case injects this interface, not `R2BlobStorageService` directly
- [X] T044 [P] [US3] Create `src/modules/intelligence/domain/value_objects/article_summary_for_report.py` frozen dataclass: `title`, `summary`, `pain_points`, `insights`, `innovations` (all Optional[str] from analyses table), `tags: List[str]` (flat tag list), `citation_count: Optional[int]`, `view_count: int`, `published_at: Optional[datetime]`; note: lives in `intelligence/domain/value_objects/` alongside existing `analysis_prompt.py` — no cross-module import needed
- [X] T045 [P] [US3] Create `src/modules/intelligence/domain/value_objects/weekly_report_prompt.py` extending `BasePrompt`; `render(topic_name: str, articles: List[ArticleSummaryForReport], week_start: date)` fills template and returns JSON-requesting prompt for `{"title": "...", "summary_text": "..."}` output
- [X] T046 [P] [US3] Create `src/modules/intelligence/domain/value_objects/image_generation_prompt.py` extending `BasePrompt`; `render(topic_name: str, top_tags: List[str], week_label: str)` returns image generation prompt string (16:9 abstract art, futuristic data visualization aesthetic)

### Implementation — Application Layer

- [X] T047 [US3] Create `src/modules/intelligence/application/use_cases/generate_weekly_report.py` orchestrating: (1) fetch top N articles via repo (COALESCE sort), (2) derive `top_tags` by frequency count, (3) `WeeklyReportPrompt().render(...)` → `LLMService.analyze()` → parse JSON title+summary, (4) `ImageGenerationPrompt().render(...)` → `ImageGenerationService.generate_image()` → `BlobStorageService.upload()`, (5) persist WeeklyReport, (6) send email+Telegram to subscribed users; depends on T040–T046

### Implementation — Infrastructure Layer

- [X] T048 [P] [US3] Create `src/infrastructure/intelligence/image/base_image_provider.py` abstract base class for image generation providers
- [X] T049 [P] [US3] Create `src/infrastructure/intelligence/image/gemini_imagen_provider.py` implementing `ImageGenerationService` using `google-genai` SDK; constructor accepts `model: str` (read from the active multimodal `LlmProvider` DB record at runtime — never hardcoded) and `api_key: str` (resolved from `api_key_env`); calls `client.models.generate_images(model=self._model, prompt=prompt, ...)`; depends on T042, T048
- [X] T050 [P] [US3] Create `src/infrastructure/storage/r2_blob_storage.py` `R2BlobStorageService` implementing `BlobStorageService` (T043) using `boto3` S3-compatible client with `R2_*` env vars; depends on T043
- [X] T051 [US3] **REWORK (2026-07-12)** Edit `src/infrastructure/intelligence/repositories/weekly_report_repo_impl.py` `WeeklyReportRepoImpl`'s article-selection query: replace the `am.citation_count` reference with a `LEFT JOIN article_metric_values ON ... AND metric_key = 'citation_count'`, ordering `COALESCE(amv.value, 0) DESC, am.view_count DESC, published_at DESC NULLS LAST` per data-model.md; `ArticleSummaryForReport` field name/type unchanged; depends on T041, T044, T006, T010

### Implementation — Notifications

- [X] T052 [P] [US3] Create `src/infrastructure/notifications/weekly_report_email_notifier.py` `WeeklyReportEmailNotifier` using `resend` Python SDK; queries `user_notification_settings` for subscribed users with `email_enabled=True`; sends HTML email per user using `RESEND_API_KEY` and `RESEND_FROM_EMAIL`; email layout matches homepage weekly report widget: full-width `cover_image_url` as header background image, semi-transparent white overlay box containing report title and summary text, CTA button "查看完整報告" / "View Full Report" linking to site root — text rendered in user's `locale` from `user_notification_settings`
- [X] T053 [P] [US3] Create `src/infrastructure/notifications/weekly_report_telegram_notifier.py` `WeeklyReportTelegramNotifier` reusing existing Telegram HTTP pattern; queries `user_notification_settings` for subscribed users with `telegram_enabled=True` and non-null `telegram_chat_id`; sends per-user message

### Implementation — Bootstrap & Entrypoint

- [X] T054 [US3] Add `build_weekly_pipeline()` to `src/bootstrap.py` wiring: `WeeklyReportRepoImpl`, `ResilientLLMService` (reuse existing builder), `GeminiImagenProvider`, `R2BlobStorageService`, `WeeklyReportEmailNotifier`, `WeeklyReportTelegramNotifier` → `GenerateWeeklyReportUseCase`; depends on T047–T053
- [X] T055 [US3] Create `src/entrypoints/cli/weekly_main.py` CLI entrypoint: (1) on startup query DB for active `type='multimodal'` provider — log error and exit(1) if none found; (2) call `build_weekly_pipeline()` and run `GenerateWeeklyReportUseCase` for each active topic with articles in the past 7 days; accepts `--topic-id` and `--week-start` CLI args for manual triggers; depends on T054

### Implementation — Backend Subscription & Notification Settings API

- [X] T056 [P] [US3] Add `GET /user/subscriptions`, `POST /user/subscriptions` (`{"topic_id": "uuid"}`), `DELETE /user/subscriptions/{topic_id}` endpoints to `backend/routers/user.py` (require_user auth)
- [X] T057 [P] [US3] Add `GET /user/notification-settings`, `PUT /user/notification-settings` endpoints to `backend/routers/user.py` (require_user auth, upsert pattern on `UserNotificationSettings`)

### Implementation — Frontend Settings UI

- [X] T058 [P] [US3] Extend `frontend/app/settings/page.tsx` with topic subscription section: list all topics, Subscribe/Unsubscribe buttons per topic, reads current subscriptions via `fetchSubscriptions()`
- [X] T059 [P] [US3] Extend `frontend/app/settings/page.tsx` with notification settings form: email_enabled toggle, telegram_chat_id text input, telegram_enabled toggle, locale select (`en` / `zh-TW`); calls `fetchNotificationSettings()` on load and `updateNotificationSettings()` on save
- [X] T060 [P] [US3] Add `fetchSubscriptions()`, `subscribeToTopic(topicId)`, `unsubscribeTopic(topicId)`, `fetchNotificationSettings()`, `updateNotificationSettings(settings)` to `frontend/lib/api/user.ts`

### Tests

- [X] T061 [P] [US3] Write unit test for `GenerateWeeklyReportUseCase` (mock LLM service, image gen, blob storage, notifiers) in `src/tests/unit/test_generate_weekly_report.py`
- [X] T062 [P] [US3] Write unit test for `GeminiImagenProvider` (mock google-genai client) in `src/tests/unit/test_gemini_imagen_provider.py`
- [X] T063 [P] [US3] Write unit test for `R2BlobStorageService` (mock boto3 client, verify upload URL construction) in `src/tests/unit/test_r2_blob_storage.py`
- [X] T064 [P] [US3] Write backend integration test for `GET/POST/DELETE /user/subscriptions` and `GET/PUT /user/notification-settings` in `backend/tests/test_user_subscriptions.py`

**Checkpoint**: Weekly report generation runs end-to-end (may use mocked R2/Imagen); subscribed users receive notifications; settings page allows subscription and notification management

---

## Phase 7: User Story 4 — View Weekly Summary Report on Homepage (Priority: P4)

**Goal**: Display latest weekly report above InlineQABar on homepage with cover image; dropdown to navigate past reports

**Independent Test**: Trigger weekly report generation via admin API, visit `/` — report appears above InlineQABar with cover image (or text-only if R2 unavailable). Open week dropdown — can navigate to past weekly reports.

### Implementation — Backend

- [X] T065 [P] [US4] Create `backend/schemas/weekly_report.py` with `WeeklyReportOut` Pydantic schema (id, topic_id, week_start_date, title, summary_text, cover_image_url, article_count, status, created_at)
- [X] T066 [P] [US4] Create `backend/services/weekly_report_service.py` with `get_weekly_reports(topic_id, limit, offset)` and `get_latest_weekly_report(topic_id)` (returns most recent `status='completed'` report) functions
- [X] T067 [US4] Create `backend/routers/weekly_reports.py` with `GET /weekly-reports` (paginated, public) and `GET /weekly-reports/latest` (single, public); depends on T065, T066
- [X] T068 [US4] Register `backend/routers/weekly_reports.py` in `backend/main.py`; depends on T067

### Implementation — Frontend

- [X] T069 [P] [US4] Create `frontend/lib/api/weekly-reports.ts` with `fetchLatestWeeklyReport(topicId: string)` and `fetchWeeklyReports(topicId: string, limit?: number, offset?: number)` using `apiFetch()`
- [X] T070 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-skeleton.tsx` loading skeleton component
- [X] T071 [P] [US4] ~~Create `frontend/components/features/weekly-report/weekly-report-card.tsx` displaying report title, summary_text (markdown rendered), and cover_image_url as CSS background-image~~ — later removed; `weekly-report-widget.tsx` renders this content inline and never adopted the component
- [X] T072 [US4] Create `frontend/components/features/weekly-report/weekly-report-widget.tsx` with week navigation dropdown (Shadcn Select); fetches via `fetchLatestWeeklyReport`/`fetchWeeklyReports`; shows "No report for this week yet" placeholder when null; uses `WeeklyReportSkeleton` while loading; depends on T069, T070, T071
- [X] T073 [US4] Extend `frontend/app/page.tsx` to render `<WeeklyReportWidget topicId={currentTopicId} />` above `<InlineQABarWrapper>`; depends on T072
- [X] T074 [P] [US4] Create `frontend/components/features/weekly-report/weekly-report-widget.stories.tsx` Storybook story (required by Constitution §II) with no-report and with-report states
- [X] T075 [P] [US4] ~~Create `frontend/components/features/weekly-report/weekly-report-card.stories.tsx` Storybook story (required by Constitution §II) with and without cover image~~ — later removed along with T071

### Tests

- [X] T076 [P] [US4] Write backend integration test for `GET /weekly-reports` and `GET /weekly-reports/latest` in `backend/tests/test_weekly_reports.py`
- [X] T077 [P] [US4] Write frontend unit test for `WeeklyReportWidget` (empty state, loaded state) in `frontend/tests/unit/weekly-report-widget.test.tsx`

**Checkpoint**: Homepage displays weekly report widget above InlineQABar; empty state shows placeholder; week dropdown navigates past reports

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation and final cross-cutting quality checks

- [X] T078 [P] Write E2E test for sort by citation_count reordering the article list in `frontend/tests/integration/sort-articles.spec.ts`
- [X] T079 [P] Write E2E test for weekly report widget display and week dropdown navigation in `frontend/tests/integration/weekly-report-widget.spec.ts`
- [X] T080 Run quickstart.md validation: applied migration 23 against a fresh throwaway DB (full upgrade chain from base, then downgrade -1, then re-upgrade — round-trip verified clean; fixed a pre-existing FK-ordering bug in downgrade() found in the process: weekly_reports was dropped before weekly_reports_translation, which FKs into it); verified `metric_definitions` seed rows present; manually ran `uv run python -m src.entrypoints.cli.refresh_metrics` against live OpenAlex/Semantic Scholar APIs and confirmed a real `article_metric_values` row was written; full `src/tests/unit/` (672 passed), `backend/tests/` unit (304 passed), and `src/tests/integration/` (50 passed) suites all green. (Note: corrected from the earlier draft — the weekly report entrypoint is `src.entrypoints.cli.weekly_report`, not `weekly_main`; not exercised end-to-end here since it requires R2/multimodal provider credentials not configured in this dev environment, but its query change (T051) is covered by existing unit tests.)

---

## Phase 9: User Story 6 — Paragraph-Level Article Citations in Weekly Report (Priority: P5, added 2026-07-12)

**Goal**: Weekly report summaries carry `[N]` inline citations resolvable to real articles (reusing the chat feature's citation UX); fixes the pre-existing `WeeklyReport.article_ids` bug (stored article titles instead of UUIDs) as a prerequisite. See spec.md FR-024–FR-029, plan.md Phase K.

**Independent Test**: Generate a weekly report for a topic with several articles. Open it on the homepage — sentences drawing on a specific article show a small numbered citation marker; clicking a marker opens that article's detail dialog. A report generated before this phase shipped still renders its summary as plain text with no markers.

### Implementation

- [X] T093 [P] [US6] Add `article_id: UUID` field to `ArticleSummaryForReport` in `src/modules/intelligence/domain/value_objects/article_summary_for_report.py`. **Extended same day (FR-035)**: replaced the old hardcoded `citation_count: Optional[int]` field with `metrics: Dict[str, float]` (deployment-agnostic catalog metrics, metric_key → value) so the object isn't tied to one specific metric name.
- [X] T094 [US6] Edit `WeeklyReportRepoImpl.fetch_top_articles()` in `src/infrastructure/persistence/intelligence/weekly_report_repo_impl.py` to additionally `SELECT Article.id` and populate `ArticleSummaryForReport.article_id`; depends on T093. **Extended same day (FR-035)**: the top-N ranking query (still ordered by `citation_count DESC, view_count DESC, published_at DESC`) no longer selects `ArticleMetricValue` directly — a second query fetches every non-NULL `article_metric_values` row for the selected article ids and groups them per-article into `ArticleSummaryForReport.metrics`, instead of filtering to `metric_key == "citation_count"` only
- [X] T095 [P] [US6] Edit `WeeklyReportPrompt.render()` in `src/modules/intelligence/domain/value_objects/weekly_report_prompt.py` to render each article with a 1-indexed bracket number (`[1]`, `[2]`, ...) and add an instruction for the LLM to cite inline via `[N]` in `summary_text`, where `N` is the article's list position (not an LLM-supplied ID). **Extended same day (FR-035)**: each article's description also renders a `Metrics:` line (humanized metric key labels + view count, omitted when neither present) plus an instruction that metrics are one input among several, not a ranking to blindly follow — see `weekly_report_repo_impl.py`'s T094 update for the query-side change and `test_weekly_report_prompt.py` for coverage
- [X] T096 [US6] Fix the `article_ids` bug in `GenerateWeeklyReportUseCase` (`src/modules/intelligence/application/use_cases/generate_weekly_report.py`, ~line 132): replace `article_ids = [str(a.title) for a in articles]` with `[str(a.article_id) for a in articles]`, order preserved so index i ↔ citation `[i+1]`; depends on T093, T094, T095
- [X] T097 [P] [US6] **CORRECTED PATH**: Edit `WeeklyReportTranslationPrompt` in `src/modules/intelligence/domain/value_objects/translation_prompt.py` (not a separate `weekly_report_translation_prompt.py` file — it lives alongside the other translation prompt value objects) to instruct the LLM to preserve `[N]` citation markers verbatim (unchanged digits, count, and position) when translating `summary_text`
- [X] T098 [US6] **CORRECTED SCOPE**: There is no standalone `TranslateWeeklyReportUseCase` — translation is handled by `GenerateWeeklyReportUseCase._translate_report()` / `_parse_translation_response()` in `src/modules/intelligence/application/use_cases/generate_weekly_report.py`. Added `_extract_citation_numbers()` and, after parsing the translated response, compare the set of `[N]` tokens against the original `report.summary_text`; on any mismatch, fall back to the original English `summary_text` for that language's translation row (title translation is kept regardless); depends on T097
- [X] T099 [P] [US6] Add `ArticleSourceOut` schema (`id: UUID`, `title: str`, `url: str`, `public_article_id: UUID`) and a `sources: List[ArticleSourceOut] = []` field on `WeeklyReportOut` in `backend/schemas/weekly_report.py`
- [X] T100 [US6] Edit `_resolve_sources()`/`_to_out()` in `backend/routers/weekly_reports.py` (now takes `db: Session`) to resolve `sources` by looking up `Article` rows for `report.article_ids` in order; wraps each entry's `UUID(...)` parse in try/except so pre-existing title-string `article_ids` are skipped (old reports resolve to an empty `sources` list, no error); all three call sites (`list_weekly_reports`, `get_latest_report`, `get_report_by_week`) updated to pass `db`; depends on T099, T096
- [X] T101 [P] [US6] Extracted `parseInline`, `renderMarkdown`, the source-chip list, and the `ArticleDetailDialog`-open-on-click logic out of `frontend/components/features/chat/AnswerDisplay.tsx` into a new shared component `frontend/components/features/chat/cited-content.tsx` exporting `<CitedContent text sources showSourceList />`; refactored `AnswerDisplay.tsx` to render via `CitedContent` (passes `showSourceList={!isLoading}` to preserve the original streaming behavior where inline citations link immediately but the chip row only appears once streaming completes)
- [X] T102 [P] [US6] Added `sources: ArticleSource[]` field to the `WeeklyReport` interface in `frontend/lib/api/weekly-reports.ts`, importing `ArticleSource` from `@/components/features/chat/types` (no import-cycle — `types.ts` has no imports). Also added `sources: []` to the existing mock objects in `frontend/tests/unit/weekly-report-widget.test.tsx` and `frontend/stories/WeeklyReportWidget.stories.tsx`
- [X] T103 [US6] Edited `frontend/components/features/weekly-report/weekly-report-widget.tsx` to render `selected.summary_text` via `<CitedContent text={selected.summary_text} sources={selected.sources} />` (wrapped in a `text-sm text-neutral-700 leading-relaxed` div for inherited typography) instead of the manual `splitParagraphs(selected.summary_text).map(p => <p>)` block; removed the now-unused `splitParagraphs` helper; depends on T101, T102

### Tests

- [X] T104 [P] [US6] Added unit tests asserting `WeeklyReportPrompt.render()` produces a 1-indexed bracketed article list, the `[N]` citation instruction, and never leaks article UUIDs into the prompt, in `src/tests/unit/modules/intelligence/domain/test_weekly_report_prompt.py` (new file, matching this repo's actual `domain/test_*.py` flat-file convention rather than a `value_objects/` subfolder); depends on T095
- [X] T105 [P] [US6] Extended `src/tests/unit/modules/intelligence/application/test_generate_weekly_report.py`: updated the `_summary()` helper to accept/generate `article_id`, and added `test_execute_populates_article_ids_with_real_uuids_in_prompt_order` — regression test for the title-string bug; depends on T096
- [X] T106 [P] [US6] **CORRECTED PATH**: Added `test_translate_report_falls_back_to_english_summary_when_citations_mismatch` and `test_translate_report_keeps_translation_when_citations_match` to the same `test_generate_weekly_report.py` (there is no separate `translate_weekly_report.py` use case to test — see T098 correction); depends on T098
- [X] T107 [P] [US6] **CORRECTED PATH**: Extended the existing `backend/tests/integration/test_weekly_reports.py` (not a new `backend/tests/test_weekly_reports.py` — that integration test already existed at this path) with `_article()` fixture helper plus `test_get_latest_resolves_sources_for_valid_article_ids` and `test_get_latest_returns_empty_sources_for_pre_existing_title_string_article_ids`; also asserted `"sources" in data` in the existing schema-fields test; depends on T100
- [X] T108 [P] [US6] **CORRECTED PATH**: Created `frontend/tests/unit/rag/CitedContent.test.tsx` (matching the existing `rag/` subfolder convention used by `AnswerDisplay.test.tsx`, not a flat `cited-content.test.tsx`) asserting `[N]` renders as a clickable marker only when within `sources` range, renders out-of-range/sourceless `[N]` as literal text, and that `showSourceList={false}` hides the chip row while still linkifying inline citations; depends on T101
- [X] T109 [P] [US6] **NO CHANGE NEEDED**: `frontend/tests/unit/rag/AnswerDisplay.test.tsx` already existed with comprehensive coverage of citation buttons, source chips, markdown, and thinking-block behavior: since `AnswerDisplay` now delegates rendering to `CitedContent` with an identical prop contract and output, this existing suite already serves as the no-regression test for the extraction — no new file created; depends on T101

**Checkpoint**: Weekly report summaries show clickable `[N]` citations resolving to the correct article; translations preserve or safely fall back on citation markers; pre-existing reports remain unaffected

---

## Phase 10: User Story 7 — Pin This Week's Report into Chat (Priority: P6, added 2026-07-12)

**Goal**: A report-level pin control on the weekly report widget bulk-adds the report's cited articles into the shared pinned-article chat context; the homepage's inline chat bar (`InlineQABarWrapper`) gains the pinning wiring it currently lacks (only the separate floating chatbot has it today). No backend or `chatbot-plugin` changes — reuses the existing `pinned_article_ids` filtered-retrieval mechanism unchanged. See spec.md FR-030–FR-034, plan.md Phase L.

**Independent Test**: Open the homepage with a weekly report displayed. Click the report's pin control — the report's cited articles appear as pinned chips near the chat input. Ask a question — the request includes those article ids. Click the pin control again — the pinned chips clear.

### Implementation

- [X] T110 [P] [US7] Extend `PinnedArticleContextValue` in `frontend/lib/providers/pinned-article-provider.tsx` with `pinArticles(articles: PinnedArticle[])` (adds any not already present, no duplicates) and `areAllPinned(ids: string[])` (true only when every given id is currently pinned); existing per-article API (`togglePinnedArticle`, `removePinnedArticle`, `clearPinnedArticles`, `isPinned`) unchanged
- [X] T111 [US7] Add a report-level pin control to `frontend/components/features/weekly-report/weekly-report-widget.tsx`: a Sparkles-style button (mirrors `article-card.tsx`'s existing per-article pin button), shown only when `selected.sources.length > 0`; toggling calls `pinArticles()` with `selected.sources` mapped to `PinnedArticle` when not fully pinned, or removes each of `selected.sources`'s ids when fully pinned (per FR-031, FR-032); depends on T110
- [X] T112 [US7] Wire `usePinnedArticle()` into `frontend/components/features/chat/InlineQABarWrapper.tsx`: build the `X-Pinned-Article-Ids` header from `pinnedArticles` exactly as `FloatingChatbotWrapper.tsx` already does; render a compact pinned-chip row above `AgentInput` showing each pinned article's title with a per-chip remove action (per FR-033); depends on T110

### Tests

- [X] T113 [P] [US7] Unit test `pinArticles()` adds only articles not already present (no duplicates) and `areAllPinned()` returns true only when every given id is present, in `frontend/tests/unit/pinned-article-provider.test.tsx`; depends on T110
- [X] T114 [P] [US7] Unit test: the weekly report widget's pin control is absent when `sources` is empty, pins all cited articles when none/some are pinned, and unpins all of them when all are already pinned, in `frontend/tests/unit/weekly-report-widget.test.tsx`; depends on T111
- [X] T115 [P] [US7] Unit test: `InlineQABarWrapper` includes `X-Pinned-Article-Ids` in the chat request headers when articles are pinned, and omits it when none are pinned, in `frontend/tests/unit/rag/InlineQABarWrapper.test.tsx`; depends on T112

**Checkpoint**: Weekly report's cited articles can be pinned into the homepage chat in one click; pinned state is visible and removable; chat requests carry the pinned article ids using the existing mechanism

---

## Phase 11: User Story 8 & 9 — Generalized Metric Display + Admin Enable/Disable (Priority: P7, added 2026-07-12)

**Goal**: Any catalog metric automatically appears as a badge on article cards/detail dialog and as a sort option, driven by a new public display-metadata endpoint; administrators can toggle a metric's enabled state from a new admin page without touching its extraction/display configuration. See spec.md FR-036–FR-042, plan.md Phase M.

**Independent Test**: With two catalog metrics enabled, open the articles list — cards show a badge per metric with correct icon/label; sort dropdown offers both. As admin, disable one metric on `/admin/metric-definitions` — it disappears from cards and sort everywhere, without a deployment.

### Implementation

- [X] T116 [US8][US9] **CORRECTED (2026-07-12)**: Migration 23 is still unshipped to production, so `icon_name` was added by editing `alembic/versions/23_article_recommendation_weekly_report.py` in place (nullable `icon_name VARCHAR(50)` column on `metric_definitions` + seed `INSERT` updated with `'quote'` for the two `citation_count` rows) — no new migration file, same rationale as the earlier citation_count/metric_definitions rework. Local Postgres (already stamped at revision 23) was brought in sync with a manual `ALTER TABLE ... ADD COLUMN` + `UPDATE` instead of a full downgrade/upgrade cycle, to avoid dropping unrelated local data.
- [X] T117 [P] [US8][US9] Add `icon_name = Column(String(50), nullable=True)` to `models/metric_definition.py`; depends on T116
- [X] T118 [P] [US8][US9] Create `backend/schemas/metric_definition.py`: `MetricDefinitionDisplayOut` (`metric_key`, `label_i18n_key`, `icon_name`, `format_hint`, `unit`), `MetricDefinitionAdminOut` (+ `id`, `provider_name`, `priority`, `enabled`), `MetricDefinitionEnabledUpdate` (`enabled: bool` only)
- [X] T119 [US8][US9] Create `backend/services/metric_definition_service.py`: `get_enabled_metric_display(db)` (dedupe by `metric_key`, ordered by `priority`), `get_all_metric_definitions(db)`, `set_metric_definition_enabled(db, id, enabled)` (updates `enabled` only, no other field accepted); depends on T117, T118
- [X] T120 [US8][US9] Create `backend/routers/metric_definitions.py`: `GET /metric-definitions` (public), `GET /admin/metric-definitions` (`require_admin`), `PATCH /admin/metric-definitions/{id}` (`require_admin`); register in `backend/main.py`; depends on T119
- [X] T121 [P] [US8] Edit `backend/schemas/article.py`: replace `citation_count: Optional[int] = None` on `ArticleOut`/`ArticleDetailOut` with `metrics: Dict[str, float] = {}`
- [X] T122 [US8] Edit `backend/services/article_service.py`: `build_article_out()` populates the generic `metrics` map (fetch every non-NULL `article_metric_values` row for the page's article ids, same two-query pattern as `WeeklyReportRepoImpl.fetch_top_articles()`); generalize `get_articles_paginated()`'s `if sort in ("citation_count", "view_count")` branch so any `sort` value matching an enabled `metric_definitions.metric_key` uses the same outerjoin+nullslast ordering, keyed dynamically instead of hardcoded; depends on T121, T117
- [X] T123 [P] [US8][US9] Create `frontend/lib/api/metric-definitions.ts`: `fetchEnabledMetricDefinitions()` (public), `fetchAllMetricDefinitions()` / `updateMetricDefinitionEnabled(id, enabled)` (admin, under `/api/proxy/admin/metric-definitions`)
- [X] T124 [P] [US8] Update `frontend/lib/api/articles.ts`'s `Article`/`ArticleDetail` types: `citation_count?: number | null` → `metrics: Record<string, number>`
- [X] T125 [P] [US8] Create `frontend/components/features/articles/metric-icons.ts` exporting a whitelisted `Record<string, LucideIcon>` + default fallback icon (e.g. `BarChart3`)
- [X] T126 [US8] Edit `article-card.tsx`: replace the hardcoded `citation_count > 0 && <Quote>` badge with a loop over `Object.entries(article.metrics)`, resolving each metric's icon/label via `fetchEnabledMetricDefinitions()` (fetched once and shared across cards, not per-card); depends on T123, T124, T125
- [X] T127 [US8] Edit `article-detail-dialog.tsx`: same generalization as T126; depends on T123, T124, T125
- [X] T128 [US8] Edit `sort-select.tsx`: fetch `fetchEnabledMetricDefinitions()` once, append one `SORT_OPTIONS` entry per returned metric after the fixed fields; depends on T123
- [X] T129 [US9] Create `frontend/app/admin/metric-definitions/page.tsx`: fetch `fetchAllMetricDefinitions()`, render one card per row grouped by `metric_key` (mirrors `admin/llm-providers/page.tsx`'s card + `Switch` pattern), toggle calls `updateMetricDefinitionEnabled()` optimistically with rollback on failure — no create/edit/delete/reorder controls; depends on T123
- [X] T130 [US9] Add the new tab to `frontend/app/settings/layout.tsx`'s admin nav list; add `admin.metricDefinitions` and related labels to `en.json`/`zh-TW.json`; depends on T129

### Tests

- [X] T131 [P] [US8][US9] Backend test: `GET /metric-definitions` returns only `enabled=true` rows, deduplicated by `metric_key`, without `provider_name`/`extractor_spec` in the response; depends on T120
- [X] T132 [P] [US8][US9] Backend test: `GET /admin/metric-definitions` and `PATCH /admin/metric-definitions/{id}` both return 401/403 for a non-admin caller; depends on T120
- [X] T133 [P] [US8][US9] Backend test: `PATCH /admin/metric-definitions/{id}` updates only `enabled`; other fields in the request body are never applied; depends on T120
- [X] T134 [P] [US8] Backend test: `GET /articles` returns a `metrics` map covering every catalog metric the article has a value for, and sorting by an enabled metric_key orders correctly with nulls-last regardless of direction; depends on T122
- [X] T135 [P] [US8] Frontend test: `article-card.tsx` renders one badge per `metrics` entry with the correct icon/label from a mocked `fetchEnabledMetricDefinitions()`, falling back to the default icon when `icon_name` is null; depends on T126
- [X] T136 [P] [US8] Frontend test: `sort-select.tsx` includes a dynamically-fetched metric option alongside the fixed fields; depends on T128
- [X] T137 [P] [US9] Frontend test: `admin/metric-definitions/page.tsx` toggles a `Switch`, calls `updateMetricDefinitionEnabled()`, and rolls back UI state if the call fails; depends on T129

**Checkpoint**: New catalog metrics require zero frontend code changes to appear on cards/detail/sort; admins can toggle metrics without a deployment; extraction/display config remains migration-only

---

## Phase 12: Metric/Provider Table Split + arXiv Citation Coverage (Priority: P7, added 2026-07-12 same day, supersedes parts of Phase 11)

**Goal**: Admin page shows one row per metric_key with zero extraction-plumbing (provider/priority) leakage; arXiv-only articles (no DOI) can get `citation_count` refreshed via Semantic Scholar's arXiv-ID lookup, which OpenAlex's API doesn't support. See spec.md's follow-up Clarifications on US8/US9, plan.md Phase N.

**Independent Test**: As admin, open `/admin/metric-definitions` — exactly one row per metric_key, no provider/priority text anywhere, with an icon dropdown and enabled toggle. Seed an article with only an `arxiv_id` (no `doi`) in metadata, run `refresh_metrics.py` against a reachable Semantic Scholar API — `citation_count` gets populated where it previously would not have been.

### Implementation

- [X] T138 [US8][US9] Edit `alembic/versions/23_article_recommendation_weekly_report.py` in place again (still unshipped): split `metric_definitions` down to metric-key-level only (`metric_key` UNIQUE, `label_i18n_key`, `format_hint`, `unit`, `icon_name`, `enabled`); add new `metric_providers` table (`metric_definition_id` FK CASCADE, `provider_name`, `priority`, `extractor_type`, `extractor_spec`, UNIQUE(metric_definition_id, provider_name)); reseed `citation_count` with one `metric_definitions` row + three `metric_providers` rows (`openalex` prio 1, `semantic_scholar` prio 2, `semantic_scholar_arxiv` prio 3); update `downgrade()` to drop `metric_providers` before `metric_definitions`. Sync local Postgres in place (hand-run equivalent DROP/CREATE/reseed, not a full downgrade/upgrade)
- [X] T139 [P] [US8][US9] Rewrite `models/metric_definition.py` to the metric-key-only shape; create `models/metric_provider.py`; register both in `models/__init__.py`; depends on T138
- [X] T140 [US8][US9] Rewrite `shared/metric_definition.py::load_enabled_metric_definitions()` to join `metric_definitions`+`metric_providers` (filtered `enabled=True`), keeping the same flat output dict shape so `resilient_metrics_service.py` needs no changes; depends on T139
- [X] T141 [P] [US8][US9] Add `SemanticScholarClient.fetch_by_arxiv_id(arxiv_id)` (`src/infrastructure/collection/clients/semantic_scholar_client.py`), same shape as `fetch_by_doi()`, hits `paper/ARXIV:<id>`
- [X] T142 [US8][US9] Add `"semantic_scholar_arxiv"` entry to `build_provider_fetchers()` (`src/infrastructure/collection/metrics/resilient_metrics_service.py`), calling `fetch_by_arxiv_id()` only when `ids.get("arxiv_id")`; no OpenAlex equivalent (its API has no arXiv-ID lookup); depends on T141
- [X] T143 [P] [US8][US9] Rewrite `backend/schemas/metric_definition.py`: `MetricDefinitionAdminOut` drops `provider_name`/`priority`; `MetricDefinitionAdminUpdate` (renamed from `MetricDefinitionEnabledUpdate`) accepts `enabled` and `icon_name`, the latter validated against a module-level `ICON_WHITELIST` via a Pydantic `field_validator`
- [X] T144 [US8][US9] Rewrite `backend/services/metric_definition_service.py`: `get_all_metric_definitions()` becomes a plain `metric_definitions` query; `update_metric_definition(db, id, *, enabled, icon_name)` (renamed from `set_metric_definition_enabled`) sets whichever field(s) are provided; depends on T139, T143
- [X] T145 [US8][US9] Update `backend/routers/metric_definitions.py`'s `PATCH /admin/metric-definitions/{id}` to use `MetricDefinitionAdminUpdate`/`update_metric_definition`; depends on T144
- [X] T146 [P] [US8][US9] Expand `frontend/components/features/articles/metric-icons.ts`'s whitelist from 8 to 20 icons (`download`, `share-2`, `bookmark`, `heart`, `message-square`, `flame`, `trophy`, `hash`, `percent`, `clock`, `book-open`, `network`); export `METRIC_ICON_NAMES: string[]`
- [X] T147 [P] [US8][US9] Update `frontend/lib/api/metric-definitions.ts`: `MetricDefinitionAdmin` drops `provider_name`/`priority`; replace `updateMetricDefinitionEnabled(id, enabled)` with `updateMetricDefinition(id, { enabled?, icon_name? })`
- [X] T148 [US8][US9] Rewrite `frontend/app/admin/metric-definitions/page.tsx`: one row per metric_key with a `Switch` (enabled) + `NativeSelect` (icon, options from `METRIC_ICON_NAMES`), both calling `updateMetricDefinition()` optimistically with rollback on failure; no provider/priority displayed; depends on T146, T147
- [X] T149 [US8][US9] Update `CLAUDE.md`: correct "LLM Provider Chain" section (no `providers.toml` file exists; DB-driven via `llm_providers` table since migration 16); add new "Metric Provider Chain" section documenting the `metric_definitions`/`metric_providers` split and contrasting it with the LLM chain; add `MetricDefinition`/`MetricProvider` to ORM Models; add missing router rows (`llm_providers.py`, `metric_definitions.py`, `weekly_reports.py`) to Backend Routers table

### Tests

- [X] T150 [P] [US8][US9] Backend integration test: `GET /admin/metric-definitions` returns exactly one row per metric_key even with multiple `metric_providers` rows, and that row exposes neither `provider_name` nor `priority`; depends on T145
- [X] T151 [P] [US8][US9] Backend integration test: `PATCH /admin/metric-definitions/{id}` accepts a whitelisted `icon_name` and persists it, rejects (422) a non-whitelisted one, and leaves the other field untouched when only one of `enabled`/`icon_name` is sent; depends on T145
- [X] T152 [P] [US8][US9] Backend integration test: `GET /articles?sort=<non-citation metric_key>` still orders correctly post-split (regression guard for T138–T140); depends on T140
- [X] T153 [P] [US8][US9] Backend unit test: `SemanticScholarClient.fetch_by_arxiv_id()` hits `paper/ARXIV:<id>`, raises `SemanticScholarRateLimitedError` on 429, returns `None` on other failures; depends on T141
- [X] T154 [P] [US8][US9] Backend unit test: `build_provider_fetchers()["semantic_scholar_arxiv"]` only calls `fetch_by_arxiv_id()` when `arxiv_id` is present; `build_provider_fetchers()["openalex"]` is never called with only an `arxiv_id` (regression guard for the original bug); depends on T142
- [X] T155 [P] [US8][US9] Frontend unit test: admin page renders one card per metric_key with no provider/priority text visible, even when the underlying fixture has multiple providers for the same metric_key; depends on T148
- [X] T156 [P] [US8][US9] Frontend unit test: changing the icon `NativeSelect` calls `updateMetricDefinition(id, { icon_name })`; toggling the `Switch` calls it with `{ enabled }`; both roll back their respective field on failure; depends on T148

**Checkpoint**: Admin page fully decoupled from extraction plumbing; arXiv-only articles are no longer silently skipped by the citation refresh job

---

## Phase 13: User Story 10 — Weekly Report Chat-Pin UX Refinements (Priority: P8, added 2026-07-14)

**Goal**: Replace one-pill-per-article pinning with one editable batch pill per report; support dragging a source pill into chat; move the pinned row below the chat input; collapse the source pill list by default; fix the stepper's date-picker drift. See spec.md FR-043–FR-051, plan.md Phase O, `docs/superpowers/specs/2026-07-14-weekly-report-chat-pinning-design.md`.

**Independent Test**: Click sparkles on a weekly report — one batch pill (not N article pills) appears below the chat input. Click its edit icon, uncheck an article — count decreases, pill disappears once all are unchecked. Expand a report's source pill list, drag one pill into the chat input — it pins as an individual pill. Resize a topic to have many weekly reports — the stepper's date picker stays put, with chevrons to jump to the newest/oldest week.

### Implementation

- [ ] T157 [P] [US10] Extend `PinnedArticleContextValue` in `frontend/lib/providers/pinned-article-provider.tsx` with `pinnedGroups: PinnedGroup[]` state (`{ id, dateLabel, articles }`) and three actions: `pinGroup(group)` (upsert by id, pin every article via existing `pinArticles`), `toggleGroupArticle(groupId, articleId)` (toggle via existing `togglePinnedArticle`; auto-remove the group once its included count hits 0), `removeGroup(groupId)` (unpin every article in the group, delete it); existing per-article API unchanged
- [ ] T158 [US10] Edit `handleTogglePinReport` in `frontend/components/features/weekly-report/weekly-report-widget.tsx` to call `pinGroup({ id: selected.id, dateLabel, articles })` / `removeGroup(selected.id)` instead of the raw `pinArticles`/loop, keeping the same `areAllPinned(ids)` branch; `dateLabel` uses the same `{ month: 'short', day: 'numeric' }` format as the stepper's week dots (T163); depends on T157
- [ ] T159 [P] [US10] Add opt-in `draggableSources?: boolean` prop (default `false`) to `frontend/components/features/chat/cited-content.tsx`; when true, wrap each source-chip button with dnd-kit's `useDraggable({ id: 'source-' + src.id, data: { article: { id, title } } })`; chat's existing usage (no `DndContext` ancestor) is unaffected by the default
- [ ] T160 [US10] Add local state `sourcesExpanded` to `weekly-report-widget.tsx` (reset to `false` on every `selected.id` change via `useEffect`); turn the existing `extraContent` article-count paragraph into a disclosure button (▸/▾) toggling it; pass `showSourceList={sourcesExpanded}` and `draggableSources` to `CitedContent`; depends on T159
- [ ] T161 [US10] Wrap `weekly-report-widget.tsx`'s returned JSX in dnd-kit's `<DndContext onDragEnd={handleDragEnd}>`; `handleDragEnd` checks `event.over?.id === 'chat-input-dropzone'` and calls `pinArticles([event.active.data.current.article])` when true; depends on T157, T159
- [ ] T162 [US10] Edit `frontend/components/features/chat/InlineQABarWrapper.tsx`: move the pinned-pills block from above `<AgentInput>` to below it; render one pill per `pinnedGroups` entry (`🌟 {dateLabel} · {includedCount} 篇文章`, live-computed from `group.articles.filter(a => isPinned(a.id)).length`) before individually-pinned articles not covered by a group; edit icon opens a shadcn `Popover` (`components/ui/popover.tsx`) with a checkbox per `group.articles` entry bound to `isPinned`, calling `toggleGroupArticle`; remove icon calls `removeGroup`; wrap the pinned-pills+input container with `useDroppable({ id: 'chat-input-dropzone' })`, highlighting it while `isOver`; depends on T157
- [ ] T163 [US10] Edit `frontend/components/features/weekly-report/weekly-report-stepper.tsx`: replace the `flex-1` spacer div with `overflow-y-auto flex-1 min-h-0` directly on the week-dots `listbox` div (with a `ref`), so the date picker stays pinned at the bottom of the column via normal flex-column order; add a `ResizeObserver` (re-checked on `reports.length` change) that shows `ChevronUp`/`ChevronDown` buttons above/below the listbox when `scrollHeight > clientHeight`, each calling `scrollTo({ top: 0 | scrollHeight, behavior: 'smooth' })`; hidden when the list fits
- [ ] T164 [P] [US10] Add `rag.weeklyGroupPill`, `rag.editGroupArticles`, `rag.groupArticlesPopoverTitle` keys to `frontend/lib/providers/locales/en.json` and `zh-TW.json`; reuse existing `rag.removeArticleRef` for the batch pill's remove-icon aria-label

### Tests

- [ ] T165 [P] [US10] Unit tests for `pinGroup`/`toggleGroupArticle` (including auto-remove-at-zero-included)/`removeGroup` in `frontend/tests/unit/pinned-article-provider.test.tsx`; depends on T157
- [ ] T166 [P] [US10] Unit test: `InlineQABarWrapper` renders a group pill with the correct live count, edit popover checkboxes reflect `isPinned`, and a simulated drop event on the dropzone pins the dragged article, in `frontend/tests/unit/rag/InlineQABarWrapper.test.tsx`; depends on T162
- [ ] T167 [P] [US10] Unit test: `weekly-report-widget.tsx`'s sparkles toggle still drives `areAllPinned` correctly through the new group actions; source pill list starts collapsed, expands on click, and resets to collapsed when `selected.id` changes, in `frontend/tests/unit/weekly-report-widget.test.tsx`; depends on T158, T160
- [ ] T168 [P] [US10] Unit test: `weekly-report-stepper.tsx`'s jump-to-top/bottom chevrons are absent when the list fits and present/functional when it overflows, in `frontend/tests/unit/weekly-report-stepper.test.tsx`; depends on T163
- [ ] T169 [P] [US10] Unit test: `cited-content.tsx`'s existing citation tests are unaffected by the new `draggableSources` prop (defaults `false`); a new test confirms drag attributes are present only when the prop is set, in `frontend/tests/unit/rag/CitedContent.test.tsx`; depends on T159

**Checkpoint**: Sparkles-pinning a weekly report produces one editable batch pill regardless of article count; source pills are draggable into chat when expanded; the pinned row sits below the chat input; the stepper's date picker no longer drifts with many weeks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1; BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (needs `ArticleMetrics` ORM T005, `MetricDefinition`/`ArticleMetricValue` ORMs T009/T010, shared loader T011)
- **US1 Recurring Metric Refresh (Phase 3, T081–T092)**: Depends on T015 (generalized `upsert()`), T011; independent of the rest of Phase 3's implementation tasks — can be built in parallel once T015 lands
- **US2 (Phase 4)**: Depends on Phase 3 (needs `article_metrics`/`article_metric_values` JOIN from T017)
- **US5 (Phase 5)**: Depends on Phase 2 (needs `UserArticleFavorite` ORM T007); can start in parallel with Phase 3/4
- **US3 (Phase 6)**: Depends on Phase 2 (needs `WeeklyReport`, `UserTopicSubscription`, `UserNotificationSettings` ORMs T006, T007); T051 additionally depends on T010 (`ArticleMetricValue` ORM); otherwise largely independent of Phase 3–5
- **US4 (Phase 7)**: Depends on Phase 6 (weekly reports must be generable for meaningful testing)
- **Polish (Phase 8)**: Depends on all user story phases
- **US6 (Phase 9, added 2026-07-12)**: Depends on Phase 7 (extends the already-displayed weekly report widget with citations); independent of Phase 8 Polish
- **US7 (Phase 10, added 2026-07-12)**: Depends on Phase 9 (needs `WeeklyReportOut.sources` to have real article ids to pin); independent of Phase 8 Polish
- **US8/US9 (Phase 11, added 2026-07-12)**: Depends on Phase 2 (needs `MetricDefinition`/`ArticleMetricValue` ORMs) and Phase 3/US1 (extends the already-shipped `citation_count` display it generalizes); independent of Phases 6–10 (weekly report / pinning)
- **US8/US9 (Phase 12, added 2026-07-12 same day)**: Depends on Phase 11 completing first (splits the table Phase 11 just built); independent of Phases 6–10
- **US10 (Phase 13, added 2026-07-14)**: Depends on Phase 10 (extends US7's pin control and reuses `InlineQABarWrapper`'s pinning wiring); independent of Phases 11–12 (metrics admin)

### User Story Dependencies

| Story | Depends On | Notes |
|-------|------------|-------|
| US1 (P1) | Phase 2 complete | No story-level dependencies. T081–T092 (recurring refresh) extend US1's "citation count visible" goal to "citation count stays fresh" |
| US2 (P2) | US1 T017 | Extends existing `article_metrics`/`article_metric_values` JOIN |
| US5 (P2) | Phase 2 complete | Shares `filter-bar.tsx` with US2; order: US2 → US5 |
| US3 (P3) | Phase 2 complete | New DDD bounded context, largely independent; T051 depends on T010 |
| US4 (P4) | US3 complete | Needs weekly reports to exist in DB |
| US6 (P5, added 2026-07-12) | US4 complete | Adds citation resolution/rendering on top of the existing weekly report pipeline and widget; also fixes the `article_ids` bug that predates US6 |
| US7 (P6, added 2026-07-12) | US6 complete | Bulk-pins US6's `sources` into the existing `usePinnedArticle` context; purely additive frontend wiring, no backend/RAG changes |
| US8/US9 (P7, added 2026-07-12) | US1 complete | Generalizes US1's citation_count-only display/sort into any enabled catalog metric, plus a narrow admin-toggle exception to FR-022; independent of US2–US7 |
| US10 (P8, added 2026-07-14) | US7 complete | Replaces US7's one-pill-per-article pinning with one editable batch pill per report, adds drag-and-drop from source pills, repositions the pinned row, collapses the source list, and fixes an unrelated stepper scroll bug; purely additive frontend wiring, no backend changes |

### 2026-07-12 Rework Note

This tasks.md was regenerated after a metrics-catalog redesign (see plan.md, research.md §9b–§9f). Tasks marked **REWORK** correspond to code that was already implemented (all originally `[X]`) against the superseded single-column `article_metrics.citation_count` design and must be edited to match the new `metric_definitions`/`article_metric_values` schema — they are unchecked again because the underlying code needs real changes, not because no work was ever done. Tasks marked **RE-VERIFY** have logic/assertions that are still valid but need to be re-run against the reworked query beneath them. New tasks (T003, T009–T011, T081–T092) are net-new capability (the recurring refresh job and its supporting abstractions) that did not exist under the original design. Everything else retains its original `[X]` and needs no changes.

### Within Each User Story

- Domain entities before services/value objects before repositories
- Backend schemas before services before routers
- Backend implementation before frontend API client
- Frontend API client before frontend components
- Implementation before tests (no TDD per project preference)

---

## Parallel Opportunities

### Phase 2 (after T004 migration is written)

T005–T011 (ORM models + shared loader) can all run in parallel with each other.

### Phase 3 (US1)

T012, T013, T014 (ScrapedArticle + scraper extensions) run in parallel.
T016, T020 (backend schema + frontend type) run in parallel.
T081, T082 (client fetch_by_doi methods) run in parallel; T083 (domain interface) can run alongside them.
T023, T024, T089, T090, T091, T092 (tests) run in parallel after their respective implementation tasks land.

### Phase 6 (US3)

T040–T046 (domain layer) run in parallel — entities, interfaces, value objects all have no inter-dependencies.
T048, T049, T050, T052, T053 (infrastructure) run in parallel after T042/T043.
T056, T057, T058, T059, T060 (backend API + frontend settings) run in parallel.
T061, T062, T063, T064 (tests) run in parallel.

### Phase 9 (US6, added 2026-07-12)

T093, T095, T097, T099, T101, T102 (independent value-object/schema/component edits) run in parallel.
T104–T109 (tests) run in parallel once their respective implementation task lands.

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
8. Phase 9 (US6, added 2026-07-12) → Weekly report citations live

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
- Migration 23 is a single revision containing all new tables and the `llm_providers.type` column + CheckConstraint — runs via `make migrate`
- Constitution §II requires Storybook stories for all new feature components (T074, T075)
- Weekly runner entrypoint (T055) deploys as Railway Cron Service: `0 8 * * 1`
- `WeeklyReportPrompt`, `ImageGenerationPrompt`, `ArticleSummaryForReport`, `WeeklyReport` entity, and all domain interfaces live in `intelligence/domain/` — weekly report is NOT a separate bounded context; it is an application of LLM + image generation inside `intelligence`
- `BlobStorageService` interface (T043) ensures the use case (T047) depends only on domain abstractions, not on R2 directly — required for hexagonal architecture compliance
- `WeeklyReportRepoImpl` lives in `src/infrastructure/intelligence/repositories/` (new subdirectory alongside existing `llm/`, `image/`, etc.)
- `user_notification_settings.locale` controls email wrapper language; supported values `'en'` and `'zh-TW'` match the app's existing i18n locales
- Multimodal provider is NOT seeded in migration 23 — admin must add via LLM provider admin UI; `weekly_main.py` validates on startup
- `metric_definitions` (unlike `llm_providers`) IS seeded in migration 23 (T004) — it has no admin UI by design (FR-022), so declarative seeding in the migration is the only way it gets populated (research.md §9d)
- `refresh_metrics.py` (T087) deploys as its own Railway Cron Service (T088): `0 3 * * *`, independent of `weekly_main.py`'s `0 8 * * 1` and independent of the backend's view_count flush — three separate schedules/processes, deliberately not sharing a runner (see plan.md Complexity Tracking)
- `ResilientMetricsService`/`MetricExtractor`/`JsonPathMetricExtractor` (T083–T085) mirror the existing `LLMService`/`ResilientLLMService`/`ProviderHandler` pattern in `src/infrastructure/intelligence/llm/` — no new architectural convention introduced
