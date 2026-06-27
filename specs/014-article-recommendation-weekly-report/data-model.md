# Data Model: Article Recommendation Signals & Weekly Summary Report

## New Tables

### `article_metrics`

Stores recommendation signals per article. 1:1 relationship with `articles`.

```sql
CREATE TABLE article_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    citation_count  INTEGER,           -- NULL if scraper doesn't provide (RSS, Blog)
    view_count      INTEGER NOT NULL DEFAULT 0,  -- Redis-flushed counter
    last_flushed_at TIMESTAMP WITH TIME ZONE,     -- last Redis → DB sync timestamp
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (article_id)
);
CREATE INDEX idx_article_metrics_article_id ON article_metrics (article_id);
CREATE INDEX idx_article_metrics_citation_count ON article_metrics (citation_count DESC NULLS LAST);
CREATE INDEX idx_article_metrics_view_count ON article_metrics (view_count DESC);
```

**ORM Model**: `models/article_metrics.py`

**Notes**:
- `citation_count = NULL` means "not available" (non-academic scrapers)
- `citation_count = 0` means the paper exists but has no citations yet
- Row is created/upserted during `ProcessScrapedArticleUseCase` after save

---

### `weekly_reports`

Stores LLM-generated weekly summaries, one per topic per week.

```sql
CREATE TABLE weekly_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id        UUID REFERENCES topics(id) ON DELETE SET NULL,
    week_start_date DATE NOT NULL,          -- Monday of the report week (UTC)
    title           TEXT NOT NULL,          -- LLM-generated title
    summary_text    TEXT NOT NULL,          -- LLM-generated summary (markdown)
    cover_image_url TEXT,                   -- R2 public URL, NULL if generation failed
    article_ids     JSONB NOT NULL DEFAULT '[]',  -- Array of included article UUIDs
    article_count   INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/completed/failed
    error_message   TEXT,                   -- populated on status='failed'
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (topic_id, week_start_date)
);
CREATE INDEX idx_weekly_reports_topic_id ON weekly_reports (topic_id);
CREATE INDEX idx_weekly_reports_week_start ON weekly_reports (week_start_date DESC);
CREATE INDEX idx_weekly_reports_status ON weekly_reports (status);
```

**ORM Model**: `models/weekly_report.py`

**Status transitions**: `pending → completed` (on success) | `pending → failed` (on any error)

---

### `user_topic_subscriptions`

Maps users to the topics they want weekly reports for.

```sql
CREATE TABLE user_topic_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    topic_id    UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, topic_id)
);
CREATE INDEX idx_user_topic_subs_user_id ON user_topic_subscriptions (user_id);
CREATE INDEX idx_user_topic_subs_topic_id ON user_topic_subscriptions (topic_id);
```

**ORM Model**: `models/user_subscription.py`

---

### `user_notification_settings`

Per-user notification channel configuration. At most one row per user (upsert on save).

```sql
CREATE TABLE user_notification_settings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email_enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    telegram_chat_id    VARCHAR(50),        -- NULL if not configured
    telegram_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    locale              VARCHAR(10) NOT NULL DEFAULT 'en',  -- 'en' | 'zh-TW'; controls email language
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id)
);
CREATE INDEX idx_user_notif_settings_user_id ON user_notification_settings (user_id);
```

**ORM Model**: Add to `models/user_subscription.py` (same file as `UserTopicSubscription`)

**`locale` usage**: The `locale` value is passed to the weekly report email notifier. The HTML email wrapper (subject line, greeting, CTA button text) is rendered in that locale. Supported values match the app's existing i18n locales (`en`, `zh-TW`).

---

## Modified Models

### `models/llm_provider.py`

Add `'multimodal'` to the accepted values for the `type` column. Update the `CheckConstraint`:

```python
type = Column(String(20), nullable=False, default='llm')
# Add CheckConstraint to allow 'llm', 'embedding', 'multimodal'
__table_args__ = (
    CheckConstraint("type IN ('llm', 'embedding', 'multimodal')", name='ck_llm_provider_type'),
)
```

The specific multimodal model (e.g., Imagen 3, Imagen 4 Ultra) is DB-configured — no model is hardcoded and no seed is added in the migration. The admin must add the multimodal provider via the existing LLM provider admin UI after deployment. `weekly_main.py` validates on startup that at least one active `type='multimodal'` provider exists and exits with a clear error if none is found.

---

### `user_article_favorites`

Records which articles a logged-in user has favorited.

```sql
CREATE TABLE user_article_favorites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    article_id  UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, article_id)
);
CREATE INDEX idx_user_article_favs_user_id ON user_article_favorites (user_id);
CREATE INDEX idx_user_article_favs_article_id ON user_article_favorites (article_id);
```

**ORM Model**: Add to `models/user_subscription.py` as `UserArticleFavorite` class.

**ON CONFLICT**: Backend `POST /user/favorites/{article_id}` uses `INSERT … ON CONFLICT DO NOTHING` to make the endpoint idempotent.

---

## Alembic Migration Sequence

```
23_article_recommendation_weekly_report.py
```

Single migration revising from `22_add_correlation_id_and_rag_providers`. Creates all four new tables (`article_metrics`, `weekly_reports`, `user_topic_subscriptions`, `user_notification_settings`, `user_article_favorites`) and adds the `type` column + `CheckConstraint` to `llm_providers` in one revision.

---

## Entity Relationships

```
auth.users
    ├── user_topic_subscriptions (user_id FK)
    │       └── topics (topic_id FK)
    ├── user_notification_settings (user_id FK, 1:1)
    └── user_article_favorites (user_id FK)
            └── articles (article_id FK)

articles
    ├── article_metrics (article_id FK, 1:1)
    └── user_article_favorites (article_id FK)

topics
    ├── weekly_reports (topic_id FK)
    └── user_topic_subscriptions (topic_id FK)

llm_providers
    └── type IN ('llm', 'embedding', 'multimodal')
```

---

## Article Selection for Weekly Report

**Sorting strategy** (applied within a 7-day window for a given `topic_id`):

```sql
ORDER BY
  COALESCE(am.citation_count, 0) DESC,
  COALESCE(am.view_count, 0) DESC,
  a.published_at DESC NULLS LAST
LIMIT :top_n  -- default 20, configurable
```

**Rationale**:
- `COALESCE(citation_count, 0)` ensures academic papers with citations rank first without excluding non-academic articles entirely (RSS/Blog articles have `citation_count = NULL`, treated as 0)
- `view_count` as secondary signal surfaces trending content among non-academic sources
- `published_at` as tiebreaker uses actual content recency (not scrape lag)
- Articles with `published_at = NULL` sink to the bottom — this is acceptable for edge-case scraper failures

---

## `ArticleSummaryForReport` Value Object

Used as per-article input to `WeeklyReportPrompt.render()`. Assembled by `WeeklyReportRepoImpl` via a JOIN across `articles`, `analyses`, and `analysis_tags`.

```python
# src/modules/intelligence/domain/value_objects/article_summary_for_report.py

@dataclass(frozen=True)
class ArticleSummaryForReport:
    title: str
    summary: Optional[str]          # from analyses.summary
    pain_points: Optional[str]      # from analyses.pain_points
    insights: Optional[str]         # from analyses.insights
    innovations: Optional[str]      # from analyses.innovations
    tags: List[str]                 # flat list of tag names from analysis_tags
    citation_count: Optional[int]   # from article_metrics (for ranking context)
    view_count: int                 # from article_metrics
    published_at: Optional[datetime]
```

**Notes**:
- Articles without an `analyses` row (analysis failed or pending) are excluded from report input — only `status='completed'` analyses are included
- `tags` is a flat list (e.g., `["transformer", "attention mechanism", "computer vision"]`), not grouped, for compact prompt representation

---

## Domain Value Objects: Prompt Types

Both live inside `src/modules/intelligence/domain/value_objects/` and extend the existing `BasePrompt` directly (no cross-module import needed — weekly report is part of `intelligence`).

### `WeeklyReportPrompt`

```python
# src/modules/intelligence/domain/value_objects/weekly_report_prompt.py

def render(
    self,
    topic_name: str,
    articles: List[ArticleSummaryForReport],
    week_start: date,
) -> 'WeeklyReportPrompt':
    ...
```

Returns JSON with `{"title": "...", "summary_text": "..."}`.

### `ImageGenerationPrompt`

```python
# src/modules/intelligence/domain/value_objects/image_generation_prompt.py

def render(
    self,
    topic_name: str,
    top_tags: List[str],   # top ~5 most frequent tags from selected articles
    week_label: str,       # e.g. "Week of June 23, 2026"
) -> 'ImageGenerationPrompt':
    ...
```

The `top_tags` list is derived by the use case (frequency count over all article tags) before calling `render()`.

---

## Domain Services

### `BlobStorageService` Interface

```python
# src/modules/intelligence/domain/services/blob_storage_service.py

class BlobStorageService(ABC):
    @abstractmethod
    def upload(self, data: bytes, key: str, content_type: str = "image/png") -> str:
        """Upload bytes to blob storage. Returns public URL."""
        ...
```

`R2BlobStorageService` in `src/infrastructure/storage/r2_blob_storage.py` implements this interface. The use case injects `BlobStorageService`, not `R2BlobStorageService` directly (hexagonal architecture: use case depends only on domain interfaces).

---

## Domain Entities (DDD)

### `src/modules/intelligence/domain/entities/weekly_report.py`

```python
@dataclass
class WeeklyReport:
    id: UUID
    topic_id: Optional[UUID]
    week_start_date: date
    title: str
    summary_text: str
    cover_image_url: Optional[str]
    article_ids: List[UUID]
    article_count: int
    status: str  # 'pending' | 'completed' | 'failed'
    error_message: Optional[str] = None
```

### Extended `Article` entity (in `collection` module)

The `Article` domain entity in `src/modules/collection/domain/` does NOT need new fields — metrics are a separate bounded context. The `article_metrics` data is fetched by the backend and included in `ArticleOut` response schema.

### `ScrapedArticle` value object (extended)

Add optional `citation_count: Optional[int] = None` to `ScrapedArticle` so scrapers can pass it through the pipeline.

---

## Backend Schema Changes

### `ArticleOut` (backend/schemas/article.py)

Add optional fields:
```python
citation_count: Optional[int] = None
view_count: int = 0
```

### `ArticleDetailOut`

Same additions as `ArticleOut` (view count especially relevant in detail view).

### New `WeeklyReportOut` schema

```python
class WeeklyReportOut(BaseModel):
    id: UUID
    topic_id: Optional[UUID]
    week_start_date: date
    title: str
    summary_text: str
    cover_image_url: Optional[str]
    article_count: int
    status: str
    created_at: datetime
```

---

## Redis Key Space

```
view:{article_id}              # INT counter — total pending views (not yet flushed)
viewed:{ip}:{article_id}       # EXISTS check — 24h TTL dedup key
```

Redis flush script scans `view:*` keys and atomically GETDEL + DB UPDATE.
