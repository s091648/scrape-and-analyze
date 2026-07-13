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

1. **Given** an article scraped via OpenAlex or Semantic Scholar, **When** the article card renders, **Then** a citation count badge is shown if citation_count > 0. Citation counts are kept fresh by a recurring background refresh, not just the value captured at scrape time.
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

### User Story 6 - Paragraph-Level Article Citations in Weekly Report (Priority: P5)

A user reading the weekly summary report wants to know exactly which article backs a specific claim, so they can click through and read the source instead of taking the LLM-generated summary on faith.

**Why this priority**: Builds directly on User Story 4 (homepage widget) — it is a trust/verifiability enhancement to an already-displayed report, not a new surface. Ships after the base weekly report pipeline is stable.

**Independent Test**: Generate a weekly report for a topic with several articles. Open the report on the homepage — sentences that draw on a specific article show a small numbered citation marker. Click the marker — the corresponding article's detail dialog opens.

**Acceptance Scenarios**:

1. **Given** a newly generated weekly report whose summary references specific articles, **When** the report is displayed, **Then** each reference appears as a small clickable numbered marker inline with the text.
2. **Given** a displayed citation marker, **When** the user clicks it, **Then** the detail view for the referenced article opens, showing its title, source, and content.
3. **Given** a weekly report translated into a non-English language, **When** the translated report is displayed, **Then** the citation markers point to the same articles as the English version (translation does not shift or drop reference numbers).
4. **Given** a weekly report generated before this capability existed, **When** it is displayed, **Then** the summary text renders normally with no citation markers (no retroactive citations, no broken markers).

---

### User Story 7 - Pin This Week's Report into Chat (Priority: P6)

A user reading the weekly report wants to ask follow-up questions about it without manually finding and pinning each article one by one, so they can go straight from "what happened this week" to "tell me more about X" in the same chat.

**Why this priority**: Builds on User Story 6 (citations) — the report's cited articles are what gets pinned. Ships after citations exist, since a report with no resolvable article identifiers has nothing meaningful to pin.

**Independent Test**: Open the homepage with a weekly report displayed. Click the report's pin control — the report's cited articles appear as pinned in the chat bar below. Ask a question — the chat response can draw on those articles' content. Click the pin control again — the pinned articles are cleared.

**Acceptance Scenarios**:

1. **Given** a weekly report is displayed with resolvable citations, **When** the user activates the report's pin control, **Then** every article the report cites is added to the chat's pinned-article context, visible as chips near the chat input.
2. **Given** a weekly report's articles are already pinned, **When** the user activates the pin control again, **Then** those articles are removed from the pinned context.
3. **Given** pinned articles from a weekly report, **When** the user sends a chat message, **Then** the request includes those articles so the assistant can draw on them, using the same mechanism already used when pinning an individual article from an article card.
4. **Given** a weekly report whose cited articles are not yet searchable in chat (not yet indexed), **When** the user pins the report and asks a question, **Then** the chat still answers using whatever pinned or general context is available — no error is shown to the user for an article that isn't indexed yet.

---

### User Story 8 - New Recommendation Metrics Automatically Appear in the Article UI (Priority: P7)

A user browsing articles wants to see whatever recommendation-signal metrics this deployment tracks (citation count, and potentially others added later like impact factor) on the article card and detail view, without those metrics being limited to whichever one happened to be hardcoded first.

**Why this priority**: Extends the already-shipped article card/detail metric display (User Story 1) so it scales with the metric catalog instead of being frozen at a single metric. Depends on the catalog and display data already existing.

**Independent Test**: With two catalog metrics enabled for a deployment (e.g. citation_count and impact_factor), open the articles list — a card for an article with both values shows two distinct badges, each with its own icon and label. Open the detail dialog — both values are visible there too. Sort dropdown includes an option for each enabled metric.

**Acceptance Scenarios**:

1. **Given** an article has a value for more than one catalog metric, **When** its card renders, **Then** a badge appears for each metric that has a value, each using that metric's own icon and label.
2. **Given** a catalog metric has no configured icon, **When** its badge renders, **Then** a sensible default icon is shown instead of a broken or missing icon.
3. **Given** the sort control, **When** the user opens it, **Then** it lists a sort option for every currently enabled catalog metric, in addition to the existing fixed fields (scraped date, published date, source, title).
4. **Given** an article has no value for a given catalog metric, **When** its card renders, **Then** no badge is shown for that metric on that card (existing per-metric "omit if absent" behavior, now generalized to any metric).

---

### User Story 9 - Administrator Enables or Disables a Recommendation Metric (Priority: P7)

A deployment administrator wants to turn a specific recommendation metric on or off for their deployment (e.g. hide impact factor on a general-audience deployment that doesn't track it meaningfully) without needing a code change or database migration for a toggle.

**Why this priority**: Builds on User Story 8 — toggling only matters once metrics can actually surface generically in the UI. Narrowly scoped: administrators can only toggle metrics the maintainer has already implemented, not define new ones.

**Independent Test**: As an admin, open the metrics settings page — every catalog metric (including currently disabled ones) is listed. Toggle one off — it stops appearing on article cards, in the detail dialog, and in the sort dropdown, without a deployment or migration.

**Acceptance Scenarios**:

1. **Given** an admin viewing the metrics settings page, **When** the page loads, **Then** every metric in the catalog is listed, grouped by metric identifier, showing its current enabled/disabled state.
2. **Given** an enabled metric, **When** the admin toggles it off, **Then** it immediately stops appearing on article cards, the detail dialog, and the sort dropdown for all users, without requiring a deployment.
3. **Given** the metrics settings page, **When** the admin views it, **Then** there is no way to create a new metric, delete an existing one, or edit its extraction/display configuration (provider, extraction rule, icon, label) — only the enabled/disabled state is editable.
4. **Given** a non-admin user, **When** they attempt to access the metrics settings page or call its underlying API, **Then** access is denied, consistent with other admin-only settings.

---

### User Story 10 - Manage Weekly Report Chat Pins as a Group, with Drag & Drop (Priority: P8)

A user who pins a weekly report's articles into chat (User Story 7) finds that every cited article shows up as its own pill, cluttering the chat input once a report has more than a couple of sources; they want one compact representation per report instead, with the ability to fine-tune which of that report's articles are actually included, and a faster way to pin a single article by dragging its pill straight into the chat input.

**Why this priority**: Builds directly on User Story 7 (pin this week's report into chat) — it's a UX refinement of the pinning interaction introduced there, not a new pinning mechanism. Ships after US7 since there's nothing to refine until bulk-pinning exists.

**Independent Test**: Open the homepage with a weekly report displayed, click sparkles — a single batch pill (not one pill per article) appears below the chat input showing the report's date and article count. Click its edit icon, uncheck one article — the pill's count decreases and that article is no longer sent to chat. Expand the report's source pill list and drag one pill into the chat input — that article is pinned as an individual pill.

**Acceptance Scenarios**:

1. **Given** a weekly report with cited articles, **When** the user activates the report's pin control, **Then** a single pill representing the batch appears below the chat input (not above it), showing the report's date and the number of currently-included articles.
2. **Given** a batch pill, **When** the user clicks its edit icon, **Then** a checklist of every article in that batch is shown, each togglable independently of the report's own sparkles control.
3. **Given** a batch pill with every article unchecked via its edit checklist, **When** the last article is unchecked, **Then** the batch pill disappears and the report's sparkles control reverts to its unpinned state.
4. **Given** a weekly report's source pill list, **When** the user drags one source pill onto the chat input, **Then** that single article is pinned as an individual pill, without affecting any existing batch pin.
5. **Given** a weekly report's source pill list with several articles, **When** the report is first displayed, **Then** the pill list is collapsed behind the existing article-count text and expands only when the user clicks it.
6. **Given** a weekly report stepper with many weeks listed, **When** the widget renders, **Then** the date picker stays in a fixed position and the week list becomes independently scrollable with jump-to-top/bottom controls, instead of the date picker drifting or being pushed out of view.

---

### Edge Cases

- What happens if a user pins from two different weekly reports (different weeks)? → Each report's sparkles activation creates its own independent batch pill; both coexist below the chat input, each individually editable/removable.
- What happens if a user unchecks every article in a batch via the edit checklist? → The batch pill disappears entirely (equivalent to fully unpinning that batch); the report's sparkles control reverts to its "not pinned" state.
- What happens if a user drags a source pill that's already pinned (individually or as part of a batch) onto the chat input? → No-op; dropping only ever adds, never duplicates or removes.
- What happens when the weekly report stepper's week list is short enough to fit without scrolling? → The jump-to-top/bottom controls are not shown.
- What happens when a scraper does not provide citation count? → `citation_count` is nullable; no badge shown. It may still be populated later by the recurring background refresh if a supported source can supply it.
- What if a recommendation-signal metric's value hasn't been refreshed recently? → The article still shows the last known value; a metric with no value yet simply omits its badge. Refresh cadence is a background concern, not user-facing.
- What if Redis is unreachable? → View count increment fails silently; DB count is used as fallback display.
- What if the LLM fails during weekly report generation? → Report is marked `status='failed'`; retry via admin API.
- What if Cloudflare R2 upload fails? → Report is saved without image; `cover_image_url` is null; report still shows in text-only form.
- What if no articles were scraped this week for a topic? → Report is skipped; no notification sent.
- What if a user has no email? (email is nullable in auth.User) → Email notification is skipped for that user; Telegram still sent if chat_id set.
- What if a guest tries to favorite an article? → Heart icon is not rendered for unauthenticated users; no API call is made.
- What if a user favorites the same article twice (race condition)? → `user_article_favorites` has a UNIQUE constraint on (user_id, article_id); second insert is a no-op (ON CONFLICT DO NOTHING).
- What if the LLM cites a reference number that doesn't correspond to any article it was given? → The marker is left as literal text (not rendered as a clickable citation); no error is surfaced to the user.
- What if a weekly report predates the citation capability (its stored article references are not valid article identifiers)? → The summary renders as plain text with no citation markers; existing reports are not regenerated or backfilled.
- What if translating a report's summary drops, adds, or renumbers a citation marker? → The translated text is discarded for that language and the original English summary is shown instead, so citations never point to the wrong article.
- What if a weekly report has no resolvable cited articles (e.g. a pre-existing report from before citations existed)? → The report's pin control has nothing to pin; it is hidden or disabled rather than pinning an empty/misleading context.
- What if some of a weekly report's cited articles aren't yet searchable in chat (not yet indexed) when the report is pinned? → Pinning still succeeds for all cited articles; unindexed ones simply contribute no retrieved content to chat answers, identical to today's behavior when an individually-pinned article isn't indexed. No error or partial-failure message is shown.
- What if the user pins a weekly report and then also pins an individual article from an article card? → Both share the same pinned-article context; pinning is additive and de-duplicated by article identifier.
- What happens when the same metric_key has multiple provider rows (e.g. citation_count via two fallback providers) — does the admin's enable/disable toggle apply per provider row or per metric_key as a whole? → Per (metric_key, provider_name) row, the same granularity as the underlying catalog table — an admin can disable one provider's contribution to a metric while leaving another provider's fallback active for that same metric, consistent with how the existing fallback-priority mechanism already works.
- What happens to already-stored values for a metric that gets disabled after articles already have values for it? → The stored values are not deleted; the metric simply stops appearing in the public display-metadata list, so its badge stops rendering everywhere and it drops out of the sort dropdown. Re-enabling it makes the same already-stored values visible again immediately.
- What happens if a user has a metric selected as their sort order and an admin disables that metric? → The sort control no longer offers it as an option; if the (now-invalid) sort value is still present in the page's state, the list falls back to the default sort rather than erroring.
- What happens when an article has only an arXiv ID and no DOI (common for preprints not yet journal-published)? → The recurring refresh still attempts to resolve `citation_count` for it, using whichever source(s) can accept an arXiv ID as a lookup key. Not every source can — this is a per-source capability, not a gap specific to any one article.
- What happens when the same underlying paper is scraped independently from more than one source (e.g. an arXiv scrape and a separate OpenAlex-discovery scrape both find it)? → Each becomes its own article record today; this feature does not attempt cross-source identity resolution (that is tracked separately as its own concern, outside this feature's scope). Each record's citation refresh proceeds independently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store `view_count` (Redis-tracked, periodically flushed to DB) per article in a separate `article_metrics` table, and MUST store `citation_count` and any other recommendation-signal metrics (e.g. future impact factor, h-index) per article in a normalized, extensible store — not as individual hardcoded columns — so that adding a new metric never requires a schema change to an existing table.
- **FR-002**: OpenAlex and Semantic Scholar scrapers MAY opportunistically populate `citation_count` at scrape time when the value is already present in the response they parsed, at no extra cost. This is a best-effort seed only — FR-020 (recurring refresh) is the authoritative mechanism that keeps the value current over the article's lifetime.
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
- **FR-020**: System MUST recurringly refresh `citation_count` (and any other catalog-defined recommendation-signal metric) for previously-scraped articles on a fixed schedule (target: at least once every 24 hours per article), independent of and without reusing the `view_count` Redis-flush mechanism, since the two have unrelated data sources and change-frequency characteristics.
- **FR-021**: The set of recommendation-signal metrics the system knows how to fetch, and which external source(s) supply each one (with fallback ordering when more than one source can supply the same metric), MUST be defined in a maintainable catalog rather than scattered across scraper-specific code, so that operators can add a new metric or a new fallback source without modifying scraper logic.
- **FR-022**: Only the repository maintainer (via code change + migration) MAY add, remove, or reconfigure entries in the metric catalog. End users and deployment administrators MUST NOT be able to define new metrics or new extraction sources through the admin dashboard or any other runtime interface — this is a deliberate scope boundary, not a temporary gap. **Amended 2026-07-12 (FR-041)**: this restriction covers a metric's extraction configuration (which external source(s) supply it, extraction rule, fallback priority) and its label — all of that remains maintainer-only. A metric's enabled/disabled state and its display icon are the two exceptions, and are administrator-editable per FR-041.
- **FR-023**: Whatever mechanism extracts a metric's value from an external source's response MUST NOT execute arbitrary stored code (e.g. no deserializing and running stored code blobs). Simple "read this field from the response" extraction MUST be expressible as inert, non-executable configuration.
- **FR-024**: The weekly report generation prompt MUST present each candidate article to the LLM with a stable 1-indexed reference number, and MUST instruct the LLM to mark any sentence that draws on a specific article with that article's reference number inline in the generated summary. The reference number identifies the article's position in the list given to the LLM — the LLM MUST NOT be asked to supply an article identifier itself, to avoid fabricated references.
- **FR-025**: The system MUST record, for each generated weekly report, the ordered list of real article identifiers corresponding 1:1 to the reference numbers used in that report's summary (reference 1 → first identifier, reference 2 → second identifier, etc.). This corrects prior behavior where the stored per-report article list did not reliably identify real articles.
- **FR-026**: When a weekly report's summary is translated into another language, the citation reference markers MUST be preserved unchanged (same numbers, same count, same meaning) in the translated text. If a translation fails to preserve them exactly, the system MUST fall back to displaying the original (English) summary for that language rather than show a translation with mismatched citations.
- **FR-027**: The system MUST expose, alongside each weekly report, enough information about each cited article (at minimum: an identifier, title, and URL) for the presentation layer to resolve a citation reference number to the specific article and let the user open it.
- **FR-028**: Weekly reports generated before this capability existed MUST continue to display without error; the system MUST NOT attempt to retroactively regenerate or backfill citation data for them, and MUST render their summary text as plain content with no citation markers.
- **FR-029**: When a user activates a citation marker in a displayed weekly report, the system MUST present the referenced article's detail (title, source, content) using the same presentation used for article citations elsewhere in the product (the existing chat feature's citation experience), so the interaction pattern is consistent across the product.
- **FR-030**: The weekly report display MUST offer a single control that adds all of the currently displayed report's cited articles to the shared pinned-article chat context in one action, using the same visual affordance (a pin/sparkles-style control) already used to pin an individual article from an article card.
- **FR-031**: Activating the report-level pin control MUST add every one of the report's cited articles to the pinned-article context (articles already pinned are left as-is, not duplicated). Activating it again once all of the report's cited articles are pinned MUST remove all of them from the pinned-article context.
- **FR-032**: The report-level pin control MUST be hidden or disabled when the currently displayed report has no cited articles to pin (e.g. a report predating citation support, per FR-028).
- **FR-033**: The homepage's chat input MUST forward the current set of pinned article identifiers to the chat backend using the same mechanism already used elsewhere in the product for pinned articles, and MUST visibly show which articles are currently pinned with a way to remove them individually.
- **FR-034**: Pinning MUST reuse the existing shared pinned-article context and existing pinned-article retrieval mechanism rather than introducing a parallel or duplicate pinning system. An article that is not yet searchable in chat when pinned MUST NOT cause an error — it simply contributes no additional context to chat answers, consistent with existing pinned-article behavior.
- **FR-035**: The weekly report generation prompt MUST present each candidate article's available recommendation-signal metric values (from the deployment's metric catalog, e.g. citation count, plus view count) to the LLM as an additional, human-readable input for judging which articles are worth covering — without hardcoding to any specific metric name, and without asserting or implying that the article list itself is ranked by importance. An article with no tracked metrics MUST be presented and judged on its content alone, not penalized for the absence.
- **FR-036**: Each metric catalog entry MUST carry a display icon identifier, defaulted by the maintainer when the metric is first added (same as its other catalog fields) but administrator-editable thereafter within a fixed, maintainer-curated set of icon options (FR-041) — an administrator MUST NOT be able to supply an icon identifier outside that set.
- **FR-037**: System MUST expose a public endpoint returning the display metadata (metric identifier, label, icon, format hint, unit) for every currently enabled catalog metric, deduplicated by metric identifier, without exposing internal extraction configuration (which provider supplies it, extraction rule, fallback priority).
- **FR-038**: The articles list and article detail APIs MUST expose a generic map of metric identifier to value covering every catalog metric that has a value for that article, replacing the single hardcoded citation-count field with a form that scales to any number of catalog metrics without further API changes.
- **FR-039**: The article card and article detail dialog MUST render a badge for every entry in an article's metric map, using the corresponding icon and label from FR-037's display metadata; a metric with no configured icon MUST fall back to a sensible default rather than rendering broken or blank.
- **FR-040**: The articles list sort control MUST include a sort option for every currently enabled catalog metric (sourced from FR-037), in addition to the existing fixed sort fields; sorting by a metric MUST rank articles by that metric's value, consistent with existing nulls-handling behavior for metric-based sorts.
- **FR-041**: Deployment administrators MAY (a) toggle whether an existing catalog metric is enabled for their deployment, and (b) change its display icon, choosing only from a fixed, maintainer-curated set of icon options — both via the admin dashboard. These are the two exceptions to metric catalog entries otherwise being maintainer-only (FR-022): administrators MUST NOT create or delete a metric, edit its label, or touch its extraction configuration (which external source(s) supply it, extraction rule, fallback priority) in any way. FR-022's restriction on defining new metrics or extraction sources remains otherwise unchanged.
- **FR-042**: The admin dashboard MUST include a page listing every metric catalog entry, including disabled ones, one row per metric — not one row per extraction source, even when a metric has more than one — showing its current enabled state and icon with controls to change both, gated by the same administrator authentication already used for other admin-only settings pages. The page MUST NOT expose which external source(s) supply a metric or their fallback order — that remains an internal implementation detail.
- **FR-043**: Activating a weekly report's pin control MUST group every article it pins into a single batch identified by that report, tracked independently of other reports' batches — a user pinning from two different weeks' reports MUST end up with two independently editable/removable batches, not one merged batch and not one pill per article.
- **FR-044**: The pinned-pills area MUST render one representative pill per batch (showing a short date label and the count of currently-included articles) instead of one pill per article in that batch. Pinned articles that do not belong to any batch (e.g. pinned individually from an article card, or via FR-049's drag-and-drop) MUST continue to render as their own individual pills alongside any batch pills.
- **FR-045**: Each batch pill MUST offer an edit control that opens a checklist of every article in that batch, letting the user include or exclude individual articles from what is actually sent to chat, without affecting other batches or individually-pinned articles.
- **FR-046**: Excluding every article in a batch via its edit checklist MUST remove the batch pill entirely and MUST be reflected in the originating report's pin control reverting to its "not pinned" state (consistent with FR-031's toggle semantics).
- **FR-047**: Each batch pill MUST also offer a control to remove the entire batch at once, equivalent to unpinning every article it currently includes.
- **FR-048**: The pinned-pills area (batch pills and individual pills together) MUST render below the chat input, not above it.
- **FR-049**: The weekly report's source-citation pill row (shown beneath a report's summary, per User Story 6) MUST be collapsed by default and expandable via the existing article-count control; when expanded, each source pill MUST be draggable, and dropping one onto the chat input MUST pin that single article additively (never duplicating or removing an existing pin).
- **FR-050**: The weekly report stepper's date picker MUST remain in a fixed position regardless of how many weeks are listed; when the week list does not fit its available space, the list itself MUST become independently scrollable rather than displacing or clipping the date picker.
- **FR-051**: When the week list is scrollable per FR-050, the stepper MUST provide controls to jump directly to the top (most recent week) or bottom (oldest week) of the list; these controls MUST NOT be shown when the list already fits without scrolling.

### Key Entities

- **ArticleMetrics**: Per-article usage signal owned by the backend — view_count, last_flushed_at. 1:1 with Article. No longer holds citation_count (see MetricDefinition / ArticleMetricValue below).
- **MetricDefinition**: One row per recommendation-signal metric (e.g. `citation_count`, future `impact_factor`) — its display metadata (label, icon, format hint, unit) and enabled/disabled state. Label is maintainer-only; icon and enabled/disabled are the two fields a deployment administrator may edit via the admin dashboard (FR-041). Does not itself describe how the metric's value is obtained — see MetricProvider.
- **MetricProvider** (split from MetricDefinition, 2026-07-12): A maintainer-curated record of one external source that can supply a value for a given metric, including its fallback priority when more than one source can supply the same metric. Multiple sources exist not because they're interchangeable (unlike LLM providers) but because (a) different articles carry different identifiers — a DOI, an arXiv ID, or both — and each source only accepts certain identifier types, and (b) independent citation databases have overlapping-but-not-identical coverage of the same paper. Entirely maintainer-only (code change + migration); never exposed to or editable by a deployment administrator.
- **ArticleMetricValue**: The current value of one catalog-defined metric for one article (e.g. this article's citation_count = 42), refreshed on a recurring schedule independent of the initial scrape. One article can have many metric values (one per tracked metric).
- **WeeklyReport**: Weekly LLM-generated summary — topic_id, week_start_date, title, summary_text, cover_image_url, status (pending/completed/failed), article_ids (JSONB array of real article identifiers, ordered so position N corresponds to citation marker [N] in summary_text — see FR-025). Reports created before citation support existed do not have reliable article_ids and are treated as citation-free (FR-028).
- **UserTopicSubscription**: user_id + topic_id (unique constraint). Tracks which topics a user wants to receive weekly reports for.
- **UserNotificationSettings**: Per-user notification config — email_enabled (bool), telegram_chat_id (nullable string), telegram_enabled (bool).
- **UserArticleFavorite**: user_id + article_id (unique constraint). Records which articles a logged-in user has favorited. No extra fields beyond timestamps.
- **LlmProvider** (extended): Add `type='multimodal'` support alongside existing `'llm'` and `'embedding'` types. Model and API key remain DB-configured, consistent with existing provider pattern.
- **PinnedGroup** (frontend-only, ephemeral — not persisted): Represents one weekly report's sparkles-pin batch (FR-043) — a report id, a short date label, and the full candidate article list for that batch (kept stable so the edit checklist can re-offer an unchecked article without re-activating the report's pin control). Lives only in `PinnedArticleProvider`'s in-memory React state, alongside (and with the same lifecycle as) the pre-existing flat pinned-article list it extends — never written to the database.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Citation counts are visible on article cards for papers from OpenAlex and Semantic Scholar within 1 scrape cycle after deployment.
- **SC-002**: View count on any article increments within 1 second of opening the article detail dialog (Redis write latency).
- **SC-003**: The articles list correctly re-sorts within the existing API response time budget (`<500ms p95`) when sorting by citation_count or view_count.
- **SC-004**: A weekly report is generated and persisted for each active topic that has at least 1 article scraped in the past 7 days.
- **SC-005**: Subscribed users with email receive the weekly report email within 5 minutes of report generation completing.
- **SC-006**: Homepage displays the current week's report or a placeholder within normal page load time.
- **SC-007**: Citation counts for previously-scraped academic articles are no more than 24 hours stale at any point in time, without requiring a re-scrape of the article.
- **SC-008**: Adding a new recommendation-signal metric to the catalog (e.g. a future impact factor) requires no changes to scraper code and no new database column for that metric.
- **SC-009**: For every weekly report generated after this capability ships, a user can click any citation marker in the summary and reach the correct source article in one click, with no dead or mismatched references.
- **SC-010**: A user can go from reading the weekly report to asking a follow-up question about its content in two actions (activate the report's pin control, then type a question) without manually locating and pinning individual articles.
- **SC-011**: Adding a new recommendation-signal metric to the catalog (extraction config + display metadata, via a single migration) requires zero changes to `article-card.tsx`, `article-detail-dialog.tsx`, or `sort-select.tsx` for the metric to appear in all three surfaces.
- **SC-012**: An administrator can disable a metric deployment-wide and see it disappear from article cards, the detail dialog, and the sort dropdown without a deployment, and can re-enable it with the same immediacy.
- **SC-013**: Pinning a weekly report with any number of cited articles always adds exactly one pill to the chat input's pinned area, regardless of how many articles the report cites.

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
- `article_metrics` rows (view_count only) are created/upserted when scrapers process articles, independent of whether any recommendation-signal metric is available.
- Citation count and other catalog-defined metrics are refreshed by a dedicated recurring background process, separate from the view_count flush — they have different data sources (external academic APIs vs. internal Redis usage counters) and are allowed to lag independently.
- The metric catalog (which metrics exist, which sources supply them) is maintainer-curated and ships via code + migration; it is not a deployment-admin-configurable or user-configurable setting in this feature. A future feature may add an admin-triggered on-demand re-run capability (e.g. "refresh this article's citation count now" from the dashboard) — that is explicitly out of scope here and does not block this feature's delivery.
- Weekly report's `article_ids` JSONB stores the top N (configurable, default 20) article IDs used to generate the summary, in the same order presented to the LLM, so citation marker [N] and `article_ids[N-1]` always agree.
- The interaction and visual style for citation markers (numbered, clickable, opens article detail) intentionally mirrors the existing chat feature's citation experience rather than introducing a new pattern, since users already learned that pattern there.
- Whether a report's cited articles are searchable in chat at pin time is not verified or surfaced to the user at pin time; this is accepted as graceful degradation consistent with how individually-pinned articles already behave when unindexed, rather than a gap that blocks User Story 7. In practice, since a weekly report only cites articles whose analysis has already completed, most cited articles have typically also completed the earlier, independent indexing step in the pipeline by the time a weekly report is generated — but this is not guaranteed and is not required for User Story 7 to be useful.
- The report-level pin control's "pinned" state reflects whether all of the report's cited articles are currently in the shared pinned-article context; a partially-pinned state (e.g. some cited articles pinned individually via their article cards, some not) is treated as "not fully pinned" and activating the control tops up the missing ones rather than leaving them out.
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

### Session 2026-07-12

- Q: `citation_count` was originally a single hardcoded column on `article_metrics`, populated inline by OpenAlex/Semantic Scholar scrapers during discover(). Does this scale as more recommendation-signal metrics get added (impact factor, h-index, altmetric, etc.)? → A: No — it does not, for two independent reasons: (1) every new metric would need a new column + scraper code change per provider that can supply it, and (2) `citation_count` drifts over time and was never being refreshed after the initial scrape. Redesigned as: `article_metrics` narrows to usage-only signals (`view_count`, owned by the backend's existing Redis-flush mechanism, unchanged); citation count and future academic metrics move to a normalized `ArticleMetricValue` store (one row per article per metric), decoupled from `article_metrics` entirely.
- Q: Where does the knowledge of "which metrics exist and which external source(s) supply each one" live? → A: In a maintainer-curated catalog (`MetricDefinition`), analogous in spirit to the existing DB-driven `LlmProvider` pattern (a `name`/provider-key column is matched against a fixed set of known implementations in code — never arbitrary code from the database). Adding a metric that only requires "read this field out of a response we already fetch" is pure catalog configuration (no code change). Adding a metric that requires new I/O (a new external API call, a new derivation) requires a one-time code change to register a new named extractor, but does not touch scraper code or existing tables.
- Q: Should extraction logic itself (e.g. "how to pull citation count out of an OpenAlex response") be stored as executable code in the database, to make it fully self-service? → A: No — rejected. Deserializing and executing stored code (e.g. pickle) from the database is a remote-code-execution risk if that data path is ever reachable by anything less than fully trusted input, and is fragile across refactors. Simple field-extraction is expressed as inert, non-executable configuration instead (FR-023); anything requiring genuine custom logic is a reviewed code change, not a stored-code entry.
- Q: Should deployment administrators be able to add new metrics or toggle which metrics are tracked from the admin dashboard? → A: No — deliberately out of scope (FR-022). The catalog is maintainer-only, shipped via code + migration. This was a scope-narrowing decision after considering (and rejecting) a self-service dashboard: the UX cost of letting admins define arbitrary provider-response field mappings (and having to surface each provider's response shape in the UI) was judged not worth it relative to the low frequency of "add a new metric" as an operation. Admins can still control which metrics exist for their own deployment only by controlling what's in their own database (via migrations), same governance model as `llm_providers`.
- Q: How does citation count stay current after the initial scrape, given it's no longer refreshed inline? → A: A new recurring background process (FR-020) refreshes catalog-defined metrics on a schedule (target: every 24h), independent of the view_count Redis-flush path. Scrapers may still opportunistically seed a metric's initial value for free if it's already present in the discover-time response, but this is a best-effort optimization, not the metric's source of truth.
- Q: Should an admin-triggered on-demand refresh (e.g. "re-run this failed metric fetch now" from the dashboard) be built as part of this feature? → A: No — explicitly deferred to a future feature. Recorded as an assumption so the recurring-refresh design isn't blocked waiting for it, and so the eventual on-demand capability is understood to need its own always-reachable service (as opposed to the recurring refresh, which can run as a scheduled job with no idle service cost) — that architectural split is a future-feature concern, not this one's.
- Q: Weekly reports currently give no indication of which article backs a given claim in the summary — should paragraph-level citations be added, and if so, in what style? → A: Yes (User Story 6). Reuse the existing chat feature's `[N]` inline citation style verbatim rather than inventing a new one: the LLM is given a numbered article list and marks claims inline with that number; the number identifies list position, not an LLM-supplied ID, to avoid fabricated references (FR-024). Clicking a marker opens the same article detail presentation already used for chat citations (FR-029), so users get one consistent citation interaction across the product.
- Q: The stored `article_ids` on `WeeklyReport` was found to actually contain article title strings, not identifiers, making it useless for resolving citations — is this in scope to fix here? → A: Yes — this is a prerequisite bug fix, not a separate feature. `article_ids` is redefined as an ordered list of real article identifiers aligned 1:1 with citation numbers (FR-025); reports generated before the fix are explicitly out of scope for backfill (FR-028) and simply display without citations.
- Q: What happens to a report's citations when it's translated into another configured language? → A: Citation markers must survive translation unchanged. If the translation step can't guarantee that (marker count/values differ from the original), the system falls back to showing the original English summary for that language rather than risk a citation pointing to the wrong article (FR-026).
- Q: Is a data migration/backfill needed so existing weekly reports gain working citations? → A: No — explicitly out of scope. Pre-existing reports keep displaying as plain summary text; only reports generated after this ships get citations (FR-028, edge cases).
- Q: Is this the full scope of citation-related work, or is more planned? → A: This is Feature 1 of a two-part plan. A follow-up feature (bringing a weekly report's own set of articles into the homepage chat as a one-click RAG context) depends on the article-identifier fix here but is out of scope for this spec update and will be scoped separately.
- Q: (Feature 3, same session) The article card / detail dialog still hardcode a single `citation_count` field end-to-end (schema, service, UI) even though the metric catalog was already generalized in the original 014 rework — should this be generalized too, so any catalog metric automatically appears in the article UI? → A: Yes (User Story 8). `ArticleOut`/`ArticleDetailOut.citation_count` becomes a generic `metrics` map (FR-038); `article-card.tsx`/`article-detail-dialog.tsx` render one badge per map entry (FR-039), driven by a new public display-metadata endpoint (FR-037) rather than hardcoded icon/label per metric. `sort-select.tsx` gains the same treatment (FR-040).
- Q: Where does a metric's display icon live, given the catalog table is keyed by `(metric_key, provider_name)` (multiple provider rows can exist per metric)? → A: On `metric_definitions` itself (FR-036), following the exact same convention already established for `label_i18n_key`/`format_hint`/`unit` on that same per-provider-row table — display metadata is expected to be identical across a metric_key's provider rows, maintainer-enforced by code review, not a new problem introduced by adding an icon field.
- Q: Should deployment administrators be able to enable/disable which catalog metrics are active, given FR-022 previously said no to any admin-facing metric catalog control? → A: Reconsidered and narrowed (FR-041 amends FR-022). The original FR-022's concern was specifically about admins *defining* new metrics or extraction sources (an RCE/self-service-dashboard-cost concern per FR-023 and the original rejection rationale) — toggling an already-maintainer-vetted metric's enabled state touches none of that risk surface, and is consistent with how `llm_providers` (a comparable maintainer-curated catalog) already has an admin dashboard (`/admin/llm-providers`) for exactly this kind of operational control. Extraction and display configuration remain maintainer-only; only `enabled` becomes administrator-editable, via a new admin page following the same `require_admin` + card/toggle UI conventions as the existing LLM provider admin page.
- Q: (Feature 2, same session) How should "pin this week's report into chat" work, given the homepage's inline chat bar currently has no pinning support at all (only the separate floating chatbot does)? → A: Reuse the existing shared pinned-article context and existing `X-Pinned-Article-Ids` pinned-retrieval mechanism end-to-end (FR-034) — no new backend/RAG pathway. The homepage's inline chat bar gains the same header-forwarding + visible pinned chips the floating chatbot already has (FR-033); the weekly report widget gains a report-level pin control (FR-030) that bulk-adds the report's cited articles (from Feature 1's `sources`) to that same context (FR-031).
- Q: What if some of a weekly report's cited articles aren't yet vectorized/indexed when pinned — does this feature need to force-ingest them or verify readiness first? → A: No — explicitly deferred. Pinning an unindexed article already degrades gracefully today (the filtered retrieval simply returns no chunks for it, no error); User Story 7 accepts the same behavior rather than adding readiness verification, forced ingestion, or user-facing warnings, since in practice most cited articles have already completed indexing by the time a weekly report is generated (indexing happens earlier in the pipeline, independent of and generally well ahead of weekly report generation).
- Q: What happens when the report is "partially pinned" (some cited articles already pinned individually, some not)? → A: Treated as not-fully-pinned; activating the report's pin control tops up the missing ones. The control only offers to remove-all once every cited article is pinned (FR-031).
- Q: (Follow-up on US8/US9, same day) The admin page was originally going to show one row per `(metric_key, provider_name)` with priority — why change to one row per `metric_key`? → A: Priority/provider are extraction implementation details an administrator has no reason to see, let alone edit — showing them was a symptom of `metric_definitions` conflating two different concerns (admin-facing display config vs. maintainer-only extraction config) in one table. Split into `MetricDefinition` (metric_key-level, admin-editable enabled/icon) and `MetricProvider` (extraction-level, maintainer-only) so the admin page can be one row per metric_key with no provider/priority leakage (FR-042).
- Q: Why does a `metric_key` ever need more than one `MetricProvider` row, if `article.source` already records which scraper found the article — couldn't the source just select the one provider to use? → A: No — `article.source` records *how an article was discovered*, which is unrelated to *where its citation data lives*. An article scraped via RSS, a blog, or arXiv can equally have a DOI worth looking up in an external citation database; conversely, arXiv itself provides no citation data at all (confirmed against the arXiv Export API — it has no citation-count field), so an arXiv-sourced article's citation count, if resolvable at all, always comes from a cross-reference database, never from its own source. The recurring refresh job therefore selects candidate articles by which identifiers they carry (DOI and/or arXiv ID) in `articles.metadata`, not by `article.source`.
- Q: Given OpenAlex and Semantic Scholar are genuinely different (non-interchangeable) citation databases, does every metric_key with an OpenAlex provider also need a matching Semantic Scholar provider, and vice versa? → A: No, only where it adds real coverage. Confirmed via each provider's public API documentation: OpenAlex's single-item lookup only accepts DOI/PMID/PMCID/MAG ID (no arXiv ID); Semantic Scholar accepts DOI or arXiv ID. `citation_count` therefore has three `MetricProvider` rows — `openalex` (DOI), `semantic_scholar` (DOI), `semantic_scholar_arxiv` (arXiv ID) — the third existing specifically so arXiv preprints without a DOI aren't silently skipped by the recurring refresh, which they previously were.
- Q: Should this feature also solve the "same paper scraped from multiple sources becomes multiple article records" problem raised above? → A: No — explicitly out of scope, already tracked as its own issue outside this feature. Recorded here only so the metric-provider design isn't misread as an attempt to solve it; each article record's citation refresh is independent regardless.
- Q: (Follow-up on FR-024) Should the weekly report prompt also give the LLM `citation_count`/`view_count` as explicit signals when it decides which articles are worth writing about, rather than relying purely on the article's title/summary/tags? → A: Yes, but generalized rather than hardcoded to `citation_count` — since citation-style metrics are deployment-defined (per the metric catalog: some deployments track `citation_count`/`impact_factor` for academic content, others track nothing beyond `view_count`), `ArticleSummaryForReport` now carries whatever catalog metrics (`article_metric_values`) exist for that article, not just citation_count. The prompt renders a `Metrics:` line per article (metric key names humanized, e.g. `citation_count` → "Citation Count") when at least one metric or a positive view count exists, and instructs the LLM to treat metrics as one input among several — not a ranking to blindly follow, and not the sole factor. The prompt deliberately does NOT claim the article list is pre-sorted by importance: with multiple independent metrics (e.g. citation_count=5+view_count=10 vs. citation_count=10+view_count=0), there is no single objective ranking to hand the LLM — that judgment is left to the LLM weighing the raw numbers alongside actual article content. The top-N candidate-selection SQL query (which 20 articles enter the prompt at all) is unaffected and still ranks by `citation_count DESC, view_count DESC, published_at DESC` — that is a separate concern from what each selected article's `Metrics:` line shows.

### Session 2026-07-14

- Q: US7's report-level pin control adds one pill per cited article to the chat input — does this scale to reports with many sources? → A: No, it clutters the chat input (User Story 10). Redesigned so one sparkles activation produces a single batch pill (FR-043, FR-044) rather than N individual pills.
- Q: If a user pins from two different weekly reports (different weeks), should the chat input show one combined pill or one pill per report? → A: One pill per report (FR-044) — each sparkles activation is independent, so pinning from week A and then week B shows two separate batch pills, each individually editable/removable.
- Q: How does a user adjust which articles within a pinned batch actually get sent to chat, short of un-pinning and re-pinning the whole report? → A: An edit (pencil) icon on the batch pill opens a checklist popover of every candidate article with a checkbox (FR-045); unchecking one removes just that article from the live pinned context while leaving it available to re-check later, without needing to re-click the report's sparkles control. Unchecking every article removes the batch pill and reverts the sparkles control to unpinned (FR-046).
- Q: Which pills should support drag-and-drop into the chat input? → A: The individual source-citation pills already shown under a weekly report's summary (FR-049); dropping one pins that single article. The batch pill itself is not a drag source in this iteration — narrower scope, revisit only if requested.
- Q: Should the source-citation pill row (User Story 6) default to expanded or collapsed? → A: Collapsed by default (FR-049), toggled via the existing "N articles" text turned into a disclosure control — a report with many cited articles otherwise dumps a wall of pills under every report shown, unrelated to whether the user actually wants to browse or drag them.
- Q: The stepper's date picker was found to drift out of position when a topic has many weekly reports — why, and what's the fix? → A: The week-dots list had no height bound or scroll, so it grew unbounded and pushed (or, inside the card's `overflow-hidden`, clipped) the date picker below it. Fixed by giving the list itself `flex-1`+`overflow-y-auto` so it scrolls internally and the date picker stays pinned at the bottom of the column regardless of week count (FR-050), plus jump-to-top/bottom chevrons shown only when the list actually overflows (FR-051).
