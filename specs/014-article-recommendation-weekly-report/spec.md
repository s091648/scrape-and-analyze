# Feature Specification: Article Recommendation Signals & Weekly Summary Report

**Feature Branch**: `014-article-recommendation-weekly-report`

**Created**: 2026-06-26

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Article Recommendation Signals (Priority: P1)

A user browsing articles wants to understand which articles are more impactful or popular to prioritize their reading.

**Why this priority**: Recommendation signals (citation count, view count) are the core value-add of this feature. Everything else builds on top of them.

**Independent Test**: Visit `/articles`, open an article that came from OpenAlex or Semantic Scholar — citation count badge appears. Click into any article detail — view count increments and is visible.

**Acceptance Scenarios**:

1. **Given** an article scraped via OpenAlex or Semantic Scholar, **When** the article card renders, **Then** a citation count badge is shown if citation_count > 0.
2. **Given** any article detail dialog is opened, **When** the user opens it, **Then** a view count is visible in the dialog and the count increments via Redis.
3. **Given** the articles list, **When** the user selects "Sort by: Citation Count" or "Sort by: Views", **Then** articles reorder accordingly.

---

### User Story 2 - Sort Articles by Recommendation Signals (Priority: P2)

A user wants to sort the article list by citation count or view count to find the most impactful articles quickly.

**Why this priority**: Sort is a standalone UI feature that directly surfaces the new metrics. Can ship without weekly reports.

**Independent Test**: Can be fully tested by opening the articles page, selecting a sort option from the sort dropdown added to the filter bar, and verifying article order changes.

**Acceptance Scenarios**:

1. **Given** the articles list page, **When** the user opens the sort dropdown, **Then** options include: Scraped At, Published At, Citation Count, View Count, Source, Title.
2. **Given** "Sort by Citation Count DESC" is selected, **When** the list loads, **Then** articles with the highest citation_count appear first.
3. **Given** a topic filter is active, **When** the sort changes, **Then** the topic filter is preserved.

---

### User Story 3 - Subscribe to a Topic for Weekly Report (Priority: P3)

A user wants to subscribe to a topic so they receive the weekly summary report automatically.

**Why this priority**: Subscription management is a prerequisite for notification delivery. Without it, weekly reports can still be generated and shown in-app.

**Independent Test**: Can be fully tested by visiting settings, subscribing to a topic, and verifying the subscription appears in the DB table.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the settings page, **When** they click "Subscribe" for a topic, **Then** a `user_topic_subscriptions` row is created.
2. **Given** a user with a Telegram chat_id set in notification settings, **When** a weekly report is generated for their subscribed topic, **Then** they receive a Telegram message.
3. **Given** a user with email set (all users have email), **When** a weekly report is generated for their subscribed topic, **Then** they receive an email notification.

---

### User Story 4 - View Weekly Summary Report on Homepage (Priority: P4)

A user visits the homepage and sees the latest weekly summary report for the default/selected topic, with a background image.

**Why this priority**: The homepage integration is the "face" of the feature but depends on weekly reports being generated first.

**Independent Test**: Can be fully tested by generating a weekly report via the admin API trigger and verifying it appears on the homepage above the InlineQABar.

**Acceptance Scenarios**:

1. **Given** a weekly report exists for the current week, **When** a user visits `/`, **Then** the report content is shown above the InlineQABar with a generated background image.
2. **Given** the weekly report widget, **When** the user opens the week dropdown, **Then** they can navigate to past weekly reports.
3. **Given** no weekly report exists yet, **When** a user visits `/`, **Then** a placeholder is shown ("No report for this week yet") and the InlineQABar remains.

---

### User Story 5 - Favorite an Article (Priority: P2)

A logged-in user wants to mark articles as favorites so they can easily find them later, including filtering the article list to show only their favorited articles.

**Why this priority**: Favorites are a high-value personal curation feature; they share the same list view as the sort feature and can ship independently as a self-contained DB + API + UI slice.

**Independent Test**: Can be fully tested by logging in, clicking the heart icon on any article card, and verifying (a) the icon fills, (b) a `user_article_favorites` row exists in the DB, (c) applying the "Favorites" filter shows only that article.

**Acceptance Scenarios**:

1. **Given** a logged-in user, **When** they click the heart icon on an article card, **Then** the icon fills (favorited state) and a row is inserted in `user_article_favorites`.
2. **Given** a favorited article, **When** the user clicks the filled heart icon again, **Then** the icon empties and the DB row is deleted (toggle behavior).
3. **Given** the filter-bar, **When** the user enables the "Favorites" filter, **Then** only articles the current user has favorited are shown.
4. **Given** a guest (unauthenticated) user, **When** they see an article card, **Then** no heart icon is shown (favorites are a logged-in-only feature).

---

### Edge Cases

- What happens when a scraper does not provide citation count? → `citation_count` is nullable; no badge shown.
- What if Redis is unreachable? → View count increment fails silently; DB count is used as fallback display.
- What if the LLM fails during weekly report generation? → Report is marked `status='failed'`; retry via admin API.
- What if Cloudflare R2 upload fails? → Report is saved without image; `cover_image_url` is null; report still shows in text-only form.
- What if no articles were scraped this week for a topic? → Report is skipped; no notification sent.
- What if a user has no email? (email is nullable in auth.User) → Email notification is skipped for that user; Telegram still sent if chat_id set.
- What if a guest tries to favorite an article? → Heart icon is not rendered for unauthenticated users; no API call is made.
- What if a user favorites the same article twice (race condition)? → `user_article_favorites` has a UNIQUE constraint on (user_id, article_id); second insert is a no-op (ON CONFLICT DO NOTHING).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store `citation_count` (from scrapers that provide it) and `view_count` (Redis-tracked, periodically flushed to DB) per article in a separate `article_metrics` table.
- **FR-002**: OpenAlex and Semantic Scholar scrapers MUST populate `citation_count` in `article_metrics` during the scrape pipeline.
- **FR-003**: Backend MUST expose a `POST /articles/{id}/view` endpoint that increments the Redis counter (deduped by IP + article_id within 24h via Redis TTL).
- **FR-004**: A background task (or scheduled flush) MUST periodically sync Redis view counts to `article_metrics.view_count` in PostgreSQL.
- **FR-005**: The articles list API (`GET /articles`) MUST support sorting by `citation_count` and `view_count` in addition to existing sort fields.
- **FR-006**: The filter-bar component MUST add a sort control (dropdown) on the right side and a "Favorites" toggle filter (logged-in users only); existing filter functionality MUST be preserved.
- **FR-007**: The system MUST provide two new DB tables: `user_topic_subscriptions` (user_id FK → auth.users, topic_id FK → topics) and `user_notification_settings` (user_id FK → auth.users, telegram_chat_id, email_enabled, telegram_enabled).
- **FR-008**: The weekly report generator MUST use `ResilientLLMService` to summarize top articles for a given topic within the past 7 days.
- **FR-009**: The weekly report generator MUST use a new image generation service (backed by a provider of `type='multimodal'` in `LlmProvider`, with model and API key configured in DB just like `llm` and `embedding` providers) to generate a cover image and upload it to Cloudflare R2.
- **FR-010**: Generated weekly reports MUST be stored in a `weekly_reports` table with fields: id, topic_id, week_start_date, title, summary_text, cover_image_url, status, created_at.
- **FR-011**: When a weekly report is created successfully, notifications MUST be sent to subscribed users: (a) in-app (all users see it on homepage), (b) email (if user has email), (c) Telegram (if user has telegram_chat_id in notification settings).
- **FR-012**: The homepage (`/`) MUST display the latest weekly report above the InlineQABar, with a dropdown to navigate to historical reports.
- **FR-013**: The `LlmProvider` model MUST support `type='multimodal'` (in addition to existing `'llm'` and `'embedding'`). The specific model and API key are DB-configured, not hardcoded; `providers.toml` defines the active multimodal provider.
- **FR-014**: A new weekly runner entrypoint (`src/entrypoints/cli/weekly_main.py`) MUST be created and deployed as a Railway Cron Service running every Monday at 8:00 UTC.
- **FR-015**: Article card and detail dialog MUST display citation count (where available) and view count badges.
- **FR-016**: A `user_article_favorites` table MUST be created (user_id FK → auth.users, article_id FK → articles, UNIQUE on (user_id, article_id)).
- **FR-017**: Backend MUST expose `POST /user/favorites/{article_id}` (add favorite) and `DELETE /user/favorites/{article_id}` (remove favorite) endpoints, both requiring `require_user` auth. `GET /user/favorites` MUST return the list of favorited article IDs for the current user.
- **FR-018**: Article card MUST display a heart icon to the left of the title (visible on hover for unfavorited; always visible when favorited) for logged-in users only. Clicking the icon toggles the favorite state.
- **FR-019**: The filter-bar MUST include a "Favorites" toggle filter that, when active, restricts the article list to only articles the current user has favorited (requires `require_user`; hidden for guest users).

### Key Entities

- **ArticleMetrics**: Per-article signals — citation_count, view_count, last_flushed_at. 1:1 with Article.
- **WeeklyReport**: Weekly LLM-generated summary — topic_id, week_start_date, title, summary_text, cover_image_url, status (pending/completed/failed), article_ids (JSONB array of included article IDs).
- **UserTopicSubscription**: user_id + topic_id (unique constraint). Tracks which topics a user wants to receive weekly reports for.
- **UserNotificationSettings**: Per-user notification config — email_enabled (bool), telegram_chat_id (nullable string), telegram_enabled (bool).
- **UserArticleFavorite**: user_id + article_id (unique constraint). Records which articles a logged-in user has favorited. No extra fields beyond timestamps.
- **LlmProvider** (extended): Add `type='multimodal'` support alongside existing `'llm'` and `'embedding'` types. Model and API key remain DB-configured, consistent with existing provider pattern.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Citation counts are visible on article cards for papers from OpenAlex and Semantic Scholar within 1 scrape cycle after deployment.
- **SC-002**: View count on any article increments within 1 second of opening the article detail dialog (Redis write latency).
- **SC-003**: The articles list correctly re-sorts within the existing API response time budget (`<500ms p95`) when sorting by citation_count or view_count.
- **SC-004**: A weekly report is generated and persisted for each active topic that has at least 1 article scraped in the past 7 days.
- **SC-005**: Subscribed users with email receive the weekly report email within 5 minutes of report generation completing.
- **SC-006**: Homepage displays the current week's report or a placeholder within normal page load time.

## Assumptions

- Railway Volumes cannot be used for blob storage; Cloudflare R2 is the blob storage provider (S3-compatible, using boto3).
- Image generation provider is registered as `type='multimodal'` in `LlmProvider`; the specific model (e.g., Gemini Imagen, DALL-E) is DB-configured via `providers.toml` and `GEMINI_API_KEY` (or equivalent), consistent with how `llm` and `embedding` providers are managed. No model is hardcoded in the spec.
- Email sending uses Resend (simple HTTP API, free tier 3000 emails/month) — new env var `RESEND_API_KEY` added to `.env.example`.
- View count deduplication: IP + article_id within 24h via Redis key TTL.
- Weekly runner is a separate Railway Cron Service (not extending the existing scraper runner), triggered every Monday at 08:00 UTC.
- `user_notification_settings` has at most one row per user (upsert pattern).
- In-app notification means the weekly report is immediately visible on the homepage; no WebSocket push is required.
- Articles with `topic_id = NULL` are excluded from weekly reports (reports are per-topic).
- The sort control and Favorites toggle are added to the existing `filter-bar.tsx` component (not new components).
- `article_metrics` rows are created/upserted when scrapers process articles; if a scraper does not provide citation_count, the row is still created with `citation_count = NULL`.
- Weekly report's `article_ids` JSONB stores the top N (configurable, default 20) article IDs used to generate the summary.
- Favorites are private to each user; no public sharing of favorite lists.
- The heart icon on article cards is hidden from guest (unauthenticated) users; requires active user session to display.

## Clarifications

### Session 2026-06-27

- Q: LlmProvider type for image generation — hardcoded model or DB-configured? → A: `type='multimodal'` (not `type='image'`); no model hardcoded. Provider model, API key, and priority all DB-configured via `providers.toml`, consistent with existing `llm`/`embedding` provider pattern.
- Q: User article favorites — required scope and UI placement? → A: New `user_article_favorites` table; heart icon left of article title (toggle on hover/click, always filled when favorited, hidden for guests); "Favorites" toggle filter added to `filter-bar.tsx`; backed by `POST/DELETE/GET /user/favorites` API endpoints.
- Q: Article selection strategy for weekly report — how to rank "top N" articles across mixed sources? → A: Option B multi-column sort: `COALESCE(citation_count, 0) DESC, view_count DESC, published_at DESC NULLS LAST`. Articles without citation data (RSS, Blog) still included but ranked below academic papers. `published_at` preferred over `scraped_at` as tiebreaker (reflects actual recency of content, not scrape lag).
- Q: Weekly report LLM prompt input — which article fields are passed per article? → A: `title`, `summary`, `pain_points`, `insights`, `innovations` (from `analyses` table) + flat tag list (from `analysis_tags`). These are assembled into an `ArticleSummaryForReport` domain value object before being passed to `WeeklyReportPrompt.render()`.
- Q: Missing DDD artifacts in `weekly_report` bounded context? → A: Three domain-layer gaps identified: (1) `BlobStorageService` abstract interface missing from `domain/services/` — `R2BlobStorageService` must implement this, not be injected directly into use case; (2) `ArticleSummaryForReport` frozen dataclass needed in `domain/value_objects/` to represent per-article prompt input; (3) `WeeklyReportPrompt` and `ImageGenerationPrompt` value objects needed in `domain/value_objects/`, following the same `BasePrompt` pattern as `AnalysisPrompt` and `ArticleTranslationPrompt` in the `intelligence` module — these live in the `weekly_report` bounded context, not in `intelligence/`.
- Q: Weekly report trigger mechanism — admin API or cron only? → A: Railway Cron Service only (`weekly_main.py` CLI entrypoint, `0 8 * * 1`). No admin trigger API. `POST /admin/weekly-reports/generate` was removed from the spec.
- Q: Image generation SDK for Google AI Studio Imagen? → A: Use `google-genai` package (not `google-generativeai`). Supports Imagen 3, 4, and 4 Ultra via `client.models.generate_images(model=model_name, ...)`. Model name read from DB at runtime; none hardcoded.
- Q: Alembic migration numbering — multiple revisions or one? → A: Single revision `23_article_recommendation_weekly_report.py` (revises `22_add_correlation_id_and_rag_providers`), containing all new tables and `llm_providers.type` column + CheckConstraint.
- Q: Default topic for WeeklyReportWidget on homepage? → A: `TopicProvider` already defaults to `data[0]` when no stored topic — `selectedTopicId` is never null after load. Widget uses `useTopic().selectedTopicId` directly; shows skeleton during load.
- Q: Multimodal provider seeding strategy? → A: No seed in migration. Admin adds the multimodal provider via existing LLM provider admin UI. `weekly_main.py` validates on startup that at least one active `type='multimodal'` provider exists and exits with error if none found.
- Q: Weekly report email template design? → A: HTML email matching homepage weekly report widget layout — full-width cover image as header background, semi-transparent white overlay box containing title + summary text, CTA button linking to site root. Subject line, greeting, and CTA text rendered in the user's `locale` from `user_notification_settings`.
- Q: Notification email locale control? → A: Add `locale VARCHAR(10) DEFAULT 'en'` to `user_notification_settings`. User sets it in the notification settings form on the settings page. Supported values: `'en'`, `'zh-TW'`.
- Q: Weekly report module placement — separate bounded context or inside `intelligence`? → A: Inside `intelligence`. Weekly report is an application of LLM text generation + image generation, which is exactly what `intelligence` encapsulates. All domain artifacts (entity, repository interface, service interfaces, value objects, use case) go in `src/modules/intelligence/`; infrastructure implementations go in `src/infrastructure/intelligence/repositories/` and `src/infrastructure/intelligence/image/`. No separate `weekly_report` module is created.
