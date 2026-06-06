# Data Model: Scheduler & Pipeline Assembly

**Feature**: 007-scheduler-pipeline
**Date**: 2026-05-29

## Entities

### Run Context (ephemeral, not persisted)

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | UUID | Unique identifier for a single pipeline invocation |
| `correlation_id` | UUID | Correlation identifier bound to all log entries and OTel spans |
| `start_time` | float | `time.time()` at pipeline start, used for duration recording |

**Lifecycle**: Created at the start of `main()`, destroyed on process exit. Stored in a `ContextVar` and structlog context.

---

### ScraperSetting (persisted, owned by 001-article-collection)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `source` | str | Display name of the scraper source |
| `source_type` | str | Type: rss, blog, arxiv |
| `url` | str | Feed URL or listing URL |
| `interval_hours` | int | Minimum hours between scrapes |
| `is_active` | bool | Whether the source is eligible for scheduling |
| `last_scraped_at` | datetime or None | Timestamp of the most recent scrape |
| `topic_id` | UUID or None | Associated topic |
| `prompt_override` | str or None | Custom analysis prompt |
| `selector_config` | SelectorConfig or None | Scraper-specific configuration |
| `keyword_items` | list[ScraperKeywordVO] or None | Keyword filter items |

**Due selection logic** (implemented in `get_active_due()` SQL):
- `is_active = True` AND (`last_scraped_at IS NULL` OR `now() - last_scraped_at > interval_hours - 30min tolerance`)

**State transitions**:
```
[never scraped] ──get_active_due()──> due
[due] ──scrape──> [scraped] (mark_scraped sets last_scraped_at)
[scraped] ──interval+tolerance elapsed──> [due]
[inactive] ──never──> excluded from due selection
```

---

### CollectionPipeline (ephemeral, assembled per run)

| Field | Type | Description |
|-------|------|-------------|
| `setting_repo` | ScraperSettingRepository | Source configuration access |
| `executor` | ScrapeExecutor | Concurrent discover/fetch engine |
| `event_bus` | InMemoryEventBus | Synchronous event dispatch |
| `scraper_factory` | ConcreteScraperFactory | Creates scrapers per setting |

**Behaviour**: `run() -> int` — discovers due sources, fetches articles, publishes events, returns count.

---

### FailedTask (persisted, owned by 001-article-collection)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `task_type` | str | analysis, tag_normalization, translation, discover |
| `payload` | JSON | Serialized task input for retry |
| `error_message` | str | Exception message |
| `created_at` | datetime | When the failure occurred |

**Relationships**: Created by `FailedTaskPersistenceHandler` in response to `AnalysisFailedEvent`, `TagNormalizationFailedEvent`, `TranslationFailedEvent`, and the discover-failed callback.

---

### InMemoryEventBus (ephemeral, assembled per run)

Event handler subscriptions (as wired in `build_collection_pipeline()`):

| Event | Handler | Result |
|-------|---------|--------|
| `ArticleScrapedEvent` | `ArticleScrapedHandler` | Processes article → `ArticleProcessedEvent` |
| `ArticleProcessedEvent` | `ArticleProcessedHandler` | Triggers analysis → `AnalysisCompletedEvent` or `AnalysisFailedEvent` |
| `AnalysisCompletedEvent` | `TagNormalizationHandler` | Normalizes tags → `TagNormalizationCompletedEvent` or `TagNormalizationFailedEvent` |
| `TagNormalizationCompletedEvent` | `AnalysisCompletedHandler` | Triggers translation for configured languages |
| `AnalysisFailedEvent` | `FailedTaskPersistenceHandler` | Persists `FailedTask` |
| `TagNormalizationFailedEvent` | `FailedTaskPersistenceHandler` | Persists `FailedTask` |
| `TranslationFailedEvent` | `FailedTaskPersistenceHandler` | Persists `FailedTask` |
| `PipelineCompletedEvent` | `OtelMetricsHandler` | Pushes OTel metrics |
| `PipelineCompletedEvent` | Notification handler | Sends Telegram notification |
