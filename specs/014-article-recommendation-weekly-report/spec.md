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

### Edge Cases

- What happens when a scraper does not provide citation count? → `citation_count` is nullable; no badge shown.
- What if Redis is unreachable? → View count increment fails silently; DB count is used as fallback display.
- What if the LLM fails during weekly report generation? → Report is marked `status='failed'`; retry via admin API.
- What if Cloudflare R2 upload fails? → Report is saved without image; `cover_image_url` is null; report still shows in text-only form.
- What if no articles were scraped this week for a topic? → Report is skipped; no notification sent.
- What if a user has no email? (email is nullable in auth.User) → Email notification is skipped for that user; Telegram still sent if chat_id set.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store `citation_count` (from scrapers that provide it) and `view_count` (Redis-tracked, periodically flushed to DB) per article in a separate `article_metrics` table.
- **FR-002**: OpenAlex and Semantic Scholar scrapers MUST populate `citation_count` in `article_metrics` during the scrape pipeline.
- **FR-003**: Backend MUST expose a `POST /articles/{id}/view` endpoint that increments the Redis counter (deduped by IP + article_id within 24h via Redis TTL).
- **FR-004**: A background task (or scheduled flush) MUST periodically sync Redis view counts to `article_metrics.view_count` in PostgreSQL.
- **FR-005**: The articles list API (`GET /articles`) MUST support sorting by `citation_count` and `view_count` in addition to existing sort fields.
- **FR-006**: The filter-bar component MUST add a sort control (dropdown) on the right side; existing filter functionality MUST be preserved.
- **FR-007**: The system MUST provide two new DB tables: `user_topic_subscriptions` (user_id FK → auth.users, topic_id FK → topics) and `user_notification_settings` (user_id FK → auth.users, telegram_chat_id, email_enabled, telegram_enabled).
- **FR-008**: The weekly report generator MUST use `ResilientLLMService` to summarize top articles for a given topic within the past 7 days.
- **FR-009**: The weekly report generator MUST use a new image generation service (backed by a provider of `type='image'` in `LlmProvider`) to generate a cover image and upload it to Cloudflare R2.
- **FR-010**: Generated weekly reports MUST be stored in a `weekly_reports` table with fields: id, topic_id, week_start_date, title, summary_text, cover_image_url, status, created_at.
- **FR-011**: When a weekly report is created successfully, notifications MUST be sent to subscribed users: (a) in-app (all users see it on homepage), (b) email (if user has email), (c) Telegram (if user has telegram_chat_id in notification settings).
- **FR-012**: The homepage (`/`) MUST display the latest weekly report above the InlineQABar, with a dropdown to navigate to historical reports.
- **FR-013**: The `LlmProvider` model MUST support `type='image'` (in addition to existing `'llm'` and `'embedding'`).
- **FR-014**: A new weekly runner entrypoint (`src/entrypoints/cli/weekly_main.py`) MUST be created and deployed as a Railway Cron Service running every Monday at 8:00 UTC.
- **FR-015**: Article card and detail dialog MUST display citation count (where available) and view count badges.

### Key Entities

- **ArticleMetrics**: Per-article signals — citation_count, view_count, last_flushed_at. 1:1 with Article.
- **WeeklyReport**: Weekly LLM-generated summary — topic_id, week_start_date, title, summary_text, cover_image_url, status (pending/completed/failed), article_ids (JSONB array of included article IDs).
- **UserTopicSubscription**: user_id + topic_id (unique constraint). Tracks which topics a user wants to receive weekly reports for.
- **UserNotificationSettings**: Per-user notification config — email_enabled (bool), telegram_chat_id (nullable string), telegram_enabled (bool).
- **LlmProvider** (extended): Add `type='image'` support alongside existing `'llm'` and `'embedding'` types.

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
- Image generation uses a Gemini Imagen model (already have `GEMINI_API_KEY`); provider registered as `type='image'` in `LlmProvider`.
- Email sending uses Resend (simple HTTP API, free tier 3000 emails/month) — new env var `RESEND_API_KEY` added to `.env.example`.
- View count deduplication: IP + article_id within 24h via Redis key TTL.
- Weekly runner is a separate Railway Cron Service (not extending the existing scraper runner), triggered every Monday at 08:00 UTC.
- `user_notification_settings` has at most one row per user (upsert pattern).
- In-app notification means the weekly report is immediately visible on the homepage; no WebSocket push is required.
- Articles with `topic_id = NULL` are excluded from weekly reports (reports are per-topic).
- The sort control is added to the existing `filter-bar.tsx` component on the right side (not a new component).
- `article_metrics` rows are created/upserted when scrapers process articles; if a scraper does not provide citation_count, the row is still created with `citation_count = NULL`.
- Weekly report's `article_ids` JSONB stores the top N (configurable, default 20) article IDs used to generate the summary.
