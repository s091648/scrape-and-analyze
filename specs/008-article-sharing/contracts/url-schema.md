# URL Schema Contract: Article Sharing

**Feature**: 008-article-sharing | **Date**: 2026-05-30

## Main Page URL (with article open)

```
/?topic=<topicId>&article=<articleId>[&<other-filters>]
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topic` | UUID string | Yes (existing) | Currently selected topic ID |
| `article` | UUID string | No | ID of the currently open article dialog |
| `page`, `sort`, `order`, etc. | string | No | Existing pagination/filter params (preserved) |

**Behavior**:
- `article` param is added via `router.replace()` when a dialog opens (no new history entry)
- `article` param is removed via `router.replace()` when the dialog closes
- On page load with `article` param present: auto-open the corresponding dialog

## Standalone Article Page

```
/articles/<articleId>
```

| Segment | Type | Description |
|---------|------|-------------|
| `articleId` | UUID string | ID of the article to display |

**Behavior**:
- Publicly accessible (no login required)
- Renders article card only — no NavBar, no FilterBar, no pagination
- Returns appropriate error state if `articleId` does not exist (404)

## Backend API (unchanged)

```
GET /articles/{article_id}
```

- Already public — no auth required
- Returns `ArticleDetailOut` (title, source, content, published_at, url, tags, tag_groups, pain_points, insights, innovations)
- Supports `?lang=<locale>` for translated content
