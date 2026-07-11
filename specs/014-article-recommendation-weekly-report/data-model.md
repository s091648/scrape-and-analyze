# Data Model: Article Recommendation Signals & Weekly Summary Report

## New Tables

### `article_metrics`

Stores the **usage** recommendation signal per article — owned entirely by the backend's Redis-flush path. 1:1 relationship with `articles`. As of the 2026-07-12 revision this table no longer holds `citation_count` (see `metric_definitions` / `article_metric_values` below) — academic/external signals and usage signals have different sources and refresh cadences and are deliberately kept in separate tables/pipelines.

```sql
CREATE TABLE article_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    view_count      INTEGER NOT NULL DEFAULT 0,  -- Redis-flushed counter
    last_flushed_at TIMESTAMP WITH TIME ZONE,     -- last Redis → DB sync timestamp
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (article_id)
);
CREATE INDEX idx_article_metrics_article_id ON article_metrics (article_id);
CREATE INDEX idx_article_metrics_view_count ON article_metrics (view_count DESC);
```

**ORM Model**: `models/article_metrics.py`

**Notes**:
- Row is created/upserted (view_count defaults to 0) during `ProcessScrapedArticleUseCase` after save, independent of whether any catalog metric is available for the article
- See research.md §9b for why `citation_count` moved out of this table

---

### `metric_definitions`

Maintainer-curated catalog of recommendation-signal metrics and how to obtain each one. Changed only via Alembic migration + code review — **never** via a runtime/admin API or dashboard (FR-022). See research.md §9b–§9d for full rationale.

```sql
CREATE TABLE metric_definitions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_key        VARCHAR(50) NOT NULL,        -- e.g. 'citation_count'
    provider_name     VARCHAR(50) NOT NULL,        -- e.g. 'openalex', 'semantic_scholar' — must match a registered fetcher (see MetricExtractor below)
    priority          INTEGER NOT NULL,            -- fallback order when multiple providers supply the same metric_key
    extractor_type    VARCHAR(20) NOT NULL,        -- 'json_path' | 'code'
    extractor_spec    JSONB NOT NULL,              -- {"path": "<jmespath expr>"} for json_path; {"key": "<registered extractor name>"} for code
    enabled           BOOLEAN NOT NULL DEFAULT TRUE,
    label_i18n_key    VARCHAR(100) NOT NULL,       -- frontend display label lookup key
    format_hint       VARCHAR(20),                 -- e.g. 'integer', 'decimal_1' — frontend rendering hint
    unit              VARCHAR(20),                 -- e.g. null, '%', nullable
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (metric_key, provider_name),
    CHECK (extractor_type IN ('json_path', 'code'))
);
CREATE INDEX idx_metric_definitions_metric_key ON metric_definitions (metric_key) WHERE enabled = TRUE;
```

**ORM Model**: `models/metric_definition.py`

**Seed data** (in the same migration, per research.md §9d):
```sql
INSERT INTO metric_definitions (metric_key, provider_name, priority, extractor_type, extractor_spec, label_i18n_key, format_hint) VALUES
('citation_count', 'openalex', 1, 'json_path', '{"path": "cited_by_count"}', 'metrics.citation_count', 'integer'),
('citation_count', 'semantic_scholar', 2, 'json_path', '{"path": "citationCount"}', 'metrics.citation_count', 'integer');
```

**Notes**:
- `provider_name` doubles as the key into a fixed in-code fetcher registry (mirrors the `LlmProvider.name` → `ClaudeProvider`/`GeminiProvider` pattern in `build_llm_service` — see `ResilientMetricsService` below). Adding a metric that only needs a *new field* from an already-registered provider's response is a pure DB insert (no deploy); adding a metric from a *new* provider requires registering a new fetcher in code once (unavoidable — fetching is I/O and cannot safely be expressed as stored data).
- `enabled = FALSE` rows are skipped entirely by `ResilientMetricsService` — this is the only "toggle," and it's maintainer/migration-controlled, not a runtime setting.

---

### `article_metric_values`

Normalized value storage — one row per `(article, metric)`. Replaces the old `article_metrics.citation_count` column. Written by `ProcessScrapedArticleUseCase` (opportunistic seed, free values only) and by `refresh_metrics.py` (authoritative recurring refresh).

```sql
CREATE TABLE article_metric_values (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id      UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    metric_key      VARCHAR(50) NOT NULL,          -- matches metric_definitions.metric_key by convention, not a DB-level FK (one metric_key can map to several metric_definitions rows — one per provider)
    value           NUMERIC,                       -- nullable; unconstrained precision to cover both integer counts and future decimal metrics (e.g. impact factor)
    last_flushed_at TIMESTAMP WITH TIME ZONE,       -- when this specific (article, metric) pair was last refreshed from its source
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (article_id, metric_key)
);
CREATE INDEX idx_article_metric_values_article_id ON article_metric_values (article_id);
CREATE INDEX idx_article_metric_values_metric_key_value ON article_metric_values (metric_key, value DESC NULLS LAST);
CREATE INDEX idx_article_metric_values_stale ON article_metric_values (last_flushed_at) WHERE last_flushed_at IS NOT NULL;
```

**ORM Model**: `models/article_metric_value.py`

**Notes**:
- `value = NULL` means "attempted, no value available" (distinct from "no row exists yet", which means "never attempted")
- `idx_article_metric_values_metric_key_value` replaces the old `idx_article_metrics_citation_count` index — used by `GET /articles?sort=citation_count` and the weekly report article-selection query
- `refresh_metrics.py`'s staleness scan is: articles missing a row for a given enabled `metric_key`, OR `last_flushed_at < now() - interval '1 day'`

---

### Expression indexes on `articles.metadata` (DOI / arxiv_id lookup)

No new columns on `articles` (keeps the hot-path table lean, per research.md §1 and §9e). Two partial expression indexes support `refresh_metrics.py`'s per-article identifier lookup:

```sql
CREATE INDEX idx_articles_metadata_doi ON articles ((metadata->>'doi')) WHERE metadata->>'doi' IS NOT NULL;
CREATE INDEX idx_articles_metadata_arxiv_id ON articles ((metadata->>'arxiv_id')) WHERE metadata->>'arxiv_id' IS NOT NULL;
```

See research.md §9e for the alternative considered (promoting to first-class columns) and why it was rejected.

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

Single migration revising from `22_add_correlation_id_and_rag_providers`. Since this migration has not shipped to production (feature branch, unreleased as of 2026-07-12), the metric-catalog rework below is folded directly into it rather than added as a follow-up revision. Creates all seven new tables (`article_metrics`, `metric_definitions`, `article_metric_values`, `weekly_reports`, `user_topic_subscriptions`, `user_notification_settings`, `user_article_favorites`), the two `articles.metadata` expression indexes (doi/arxiv_id), seeds `metric_definitions` with the initial OpenAlex/Semantic Scholar citation_count rows, and adds the `type` column + `CheckConstraint` to `llm_providers` — all in one revision.

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
    ├── article_metrics (article_id FK, 1:1) — view_count only
    ├── article_metric_values (article_id FK, 1:N — one row per tracked metric_key)
    └── user_article_favorites (article_id FK)

metric_definitions
    └── metric_key referenced by convention (not FK) from article_metric_values.metric_key

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
  COALESCE(amv.value, 0) DESC,   -- amv = article_metric_values JOIN ... AND metric_key = 'citation_count'
  COALESCE(am.view_count, 0) DESC,
  a.published_at DESC NULLS LAST
LIMIT :top_n  -- default 20, configurable
```

`amv` is a `LEFT JOIN article_metric_values ON article_metric_values.article_id = a.id AND article_metric_values.metric_key = 'citation_count'` (replaces the old direct `am.citation_count` column reference — `am` here still refers to `article_metrics` for `view_count` only).

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
    citation_count: Optional[int]   # from article_metric_values WHERE metric_key='citation_count' (for ranking context)
    view_count: int                 # from article_metrics
    published_at: Optional[datetime]
```

**Notes**:
- Articles without an `analyses` row (analysis failed or pending) are excluded from report input — only `status='completed'` analyses are included
- `tags` is a flat list (e.g., `["transformer", "attention mechanism", "computer vision"]`), not grouped, for compact prompt representation
- As of 2026-07-12, `citation_count` is populated via a join against `article_metric_values` rather than a flat column — the field name and type on this value object are unchanged, only `WeeklyReportRepoImpl`'s query changes

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

### `MetricExtractor` Interface + `ResilientMetricsService` (new, 2026-07-12)

Mirrors the existing `LLMService`/`ResilientLLMService` pattern (`src/infrastructure/intelligence/llm/`) so the same DDD shape and fallback semantics are reused rather than inventing a parallel convention.

```python
# src/modules/collection/domain/services/metric_extractor.py

class MetricExtractor(ABC):
    @abstractmethod
    def fetch(self, article_identifiers: dict[str, str]) -> Optional[dict]:
        """Fetch the raw response for one article from this extractor's source.
        article_identifiers e.g. {"doi": "...", "arxiv_id": "..."} — extractor uses whichever key it needs."""

    @abstractmethod
    def extract(self, raw_response: dict, extractor_spec: dict) -> Optional[Any]:
        """Pull the metric value out of a raw response already fetched via fetch()."""
```

Two concrete implementations in `src/infrastructure/collection/metrics/`:
- `JsonPathMetricExtractor` — generic; `extract()` evaluates `extractor_spec["path"]` (a JMESPath expression) against `raw_response` via the `jmespath` library. `fetch()` delegates to a `provider_name`-keyed fetcher (see below).
- Named `code`-type extractors (e.g. a future `CrossrefImpactFactorExtractor`) — both `fetch()` and `extract()` fully custom, registered by name in a fixed in-code dict, looked up via `extractor_spec["key"]`.

`provider_name` → fetcher mapping (new methods on existing clients, not new classes — see research.md §9f):
```python
PROVIDER_FETCHERS: dict[str, Callable[[dict], Optional[dict]]] = {
    "openalex": lambda ids: openalex_client.fetch_by_doi(ids["doi"]) if ids.get("doi") else None,
    "semantic_scholar": lambda ids: semantic_scholar_client.fetch_by_doi(ids["doi"]) if ids.get("doi") else None,
}
```

`ResilientMetricsService` (`src/infrastructure/collection/metrics/resilient_metrics_service.py`) is built at bootstrap by reading `metric_definitions` from DB (new `shared/metric_definition.py::load_enabled_metric_definitions(session)`, same shape/location as `shared/llm_provider.py::load_active_providers`), grouped by `metric_key`, ordered by `priority`. For a given article's identifiers, `fetch_all(article_identifiers: dict) -> dict[str, Any]` walks each `metric_key` group in priority order, tries each provider's fetch+extract, keeps the first successful non-null value, moves to the next `metric_key`. This is the single call site both `refresh_metrics.py` uses for the recurring refresh.

**Not part of this abstraction**: the opportunistic free-seed at scrape time (`ProcessScrapedArticleUseCase` forwarding `ScrapedArticle.metadata` keys) does not go through `ResilientMetricsService` — it's a direct, zero-cost passthrough of whatever the scraper already parsed, unrelated to the catalog-driven fetch/extract cycle.

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

The `Article` domain entity (`src/shared/domain/entities/article.py`) does NOT need new fields — metrics are a separate bounded context, and DOI/arxiv_id continue to live inside its existing `metadata` dict (see research.md §9e). The `article_metrics` / `article_metric_values` data is fetched by the backend and included in the `ArticleOut` response schema.

### `ScrapedArticle` value object (revised 2026-07-12)

`ScrapedArticle` (`src/modules/collection/domain/value_objects/scraped_article.py`) already carries a single `citation_count: Optional[int] = None` field from earlier work on this branch — this is now generalized to `metric_seeds: Dict[str, Any] = field(default_factory=dict)` so any scraper can opportunistically pass along multiple free-value metrics (not just citation_count) without adding a new dataclass field per metric. `openalex_scraper.py` / `semantic_scholar_scraper.py` populate `metric_seeds={"citation_count": e.citation_count}` where they previously set the dedicated field. `ProcessScrapedArticleUseCase` forwards `metric_seeds` (filtered to known `metric_definitions.metric_key` values) to the generalized `ArticleMetricsRepository.upsert(article_id, metrics: dict[str, Any])`.

### `ArticleMetricsRepository` (generalized)

`src/modules/collection/domain/repositories/article_metrics_repository.py` — `upsert()` signature changes from `upsert(article_id: UUID, citation_count: Optional[int]) -> None` to `upsert(article_id: UUID, metrics: dict[str, Any]) -> None`. `SqlAlchemyArticleMetricsRepository` (`src/infrastructure/persistence/collection/article_metrics_repo_impl.py`) now writes one row per key into `article_metric_values` via `INSERT ... ON CONFLICT (article_id, metric_key) DO UPDATE SET value = EXCLUDED.value, last_flushed_at = now()`, instead of updating a single `citation_count` column. `view_count`/`article_metrics` upsert (unrelated to this repository — owned by the backend) is untouched.

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
