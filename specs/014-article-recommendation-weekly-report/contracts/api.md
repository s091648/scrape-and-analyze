# API Contracts: Article Recommendation Signals & Weekly Summary Report

All endpoints follow existing patterns: FastAPI router, `apiFetch()` on frontend, proxy via `/api/proxy/[...path]`.

## Extended Endpoints

### `GET /articles` (extended)

Add two new sort values to the existing `sort` query param:

```
sort: "scraped_at" | "published_at" | "source" | "title" | "citation_count" | "view_count"
order: "asc" | "desc"
```

Response `ArticleOut` gains:
```json
{
  "id": "uuid",
  "citation_count": 42,   // null if not available
  "view_count": 118,      // 0 if never viewed
  ...existing fields
}
```

### `GET /articles/{id}` (extended)

Response `ArticleDetailOut` gains same `citation_count` and `view_count` fields.

---

## New Endpoints

### `POST /articles/{id}/view`

Track a view event for an article. Increments Redis counter (deduped by client IP within 24h).

**Request**: No body required. Client IP read from `X-Forwarded-For` header (set by Railway proxy).

**Response**: `204 No Content`

**Auth**: Public (same as article reads).

**Rate limiting**: Redis dedup key `viewed:{ip}:{article_id}` with 24h TTL; endpoint returns 204 regardless (no error on duplicate view).

---

### `GET /weekly-reports`

List weekly reports for a topic.

**Query params**:
```
topic_id: UUID (required)
limit: int = 10
offset: int = 0
```

**Response**:
```json
{
  "items": [WeeklyReportOut],
  "total": 42
}
```

### `GET /weekly-reports/latest`

Get the most recent completed weekly report for a topic.

**Query params**:
```
topic_id: UUID (required)
```

**Response**: `WeeklyReportOut | null`

### `POST /admin/weekly-reports/generate` (admin only)

Trigger weekly report generation for a specific topic and week.

**Request body**:
```json
{
  "topic_id": "uuid",
  "week_start_date": "2026-06-22"  // Monday ISO date
}
```

**Response**: `WeeklyReportOut` (status='pending' initially; generation is async)

**Auth**: `require_admin`

---

### `GET /user/subscriptions` (authenticated)

Get the current user's topic subscriptions.

**Response**:
```json
{
  "subscriptions": [
    { "topic_id": "uuid", "topic_name": "string", "created_at": "datetime" }
  ]
}
```

**Auth**: `require_user`

### `POST /user/subscriptions`

Subscribe to a topic.

**Request body**: `{ "topic_id": "uuid" }`

**Response**: `201 Created` with `{ "id": "uuid", "topic_id": "uuid" }`

**Auth**: `require_user`

### `DELETE /user/subscriptions/{topic_id}`

Unsubscribe from a topic.

**Response**: `204 No Content`

**Auth**: `require_user`

---

### `GET /user/notification-settings` (authenticated)

Get the current user's notification settings.

**Response**:
```json
{
  "email_enabled": true,
  "telegram_chat_id": "123456789",
  "telegram_enabled": false
}
```

**Auth**: `require_user`

### `PUT /user/notification-settings`

Upsert notification settings.

**Request body**:
```json
{
  "email_enabled": true,
  "telegram_chat_id": "123456789",
  "telegram_enabled": true
}
```

**Response**: `200 OK` with updated settings.

**Auth**: `require_user`

---

## Frontend API Client Changes

New functions in `frontend/lib/api/`:
- `weekly-reports.ts` — `fetchLatestWeeklyReport(topicId)`, `fetchWeeklyReports(topicId, limit, offset)`
- `articles.ts` (extended) — `recordArticleView(id)` (fire-and-forget)
- `user.ts` (extended or new) — `fetchSubscriptions()`, `subscribeToTopic(topicId)`, `unsubscribeTopic(topicId)`, `fetchNotificationSettings()`, `updateNotificationSettings(settings)`

## Frontend Component Changes

### New components
- `components/features/weekly-report/WeeklyReportWidget.tsx` — report display with dropdown
- `components/features/weekly-report/WeeklyReportCard.tsx` — report content card with cover image background
- `components/features/weekly-report/WeeklyReportSkeleton.tsx` — loading state

### Modified components
- `components/features/articles/filter-bar.tsx` — add sort dropdown (right side, immediate apply)
- `components/features/articles/article-card.tsx` — show citation_count badge, view_count badge
- `components/features/articles/article-detail-dialog.tsx` — show citation_count + view_count, fire POST /articles/{id}/view on open
- `app/page.tsx` — add `WeeklyReportWidget` above `InlineQABarWrapper`
- `app/settings/page.tsx` — add topic subscription UI and notification settings form
