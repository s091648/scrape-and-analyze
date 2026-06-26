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
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id)
);
CREATE INDEX idx_user_notif_settings_user_id ON user_notification_settings (user_id);
```

**ORM Model**: Add to `models/user_subscription.py` (same file as `UserTopicSubscription`)

---

## Modified Models

### `models/llm_provider.py`

Add `'image'` to the accepted values for the `type` column. Update the `CheckConstraint`:

```python
type = Column(String(20), nullable=False, default='llm')
# Add CheckConstraint to allow 'llm', 'embedding', 'image'
__table_args__ = (
    CheckConstraint("type IN ('llm', 'embedding', 'image')", name='ck_llm_provider_type'),
)
```

Note: The existing `providers.toml` must also be updated to register image providers.

---

## Alembic Migration Sequence

```
18_article_metrics_table.py
19_weekly_reports_table.py
20_user_subscription_tables.py
21_llm_provider_type_image.py
```

Each migration is independent. Migrations 18–20 are additive (new tables); migration 21 adds a constraint to an existing table.

---

## Entity Relationships

```
auth.users
    ├── user_topic_subscriptions (user_id FK)
    │       └── topics (topic_id FK)
    └── user_notification_settings (user_id FK, 1:1)

articles
    └── article_metrics (article_id FK, 1:1)

topics
    ├── weekly_reports (topic_id FK)
    └── user_topic_subscriptions (topic_id FK)

llm_providers
    └── type IN ('llm', 'embedding', 'image')
```

---

## Domain Entities (DDD)

### `src/modules/weekly_report/domain/entities/weekly_report.py`

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
