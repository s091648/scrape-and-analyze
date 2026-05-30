# Data Model: Article Collection

**Phase**: 1
**Date**: 2026-05-28

## Entity Overview

```
ScraperSetting (DB)
    │  configures
    ▼
ScrapeJob ──────────────── DiscoverTask
    │  fetched by                │
    ▼                            ▼ (executor)
ScrapedArticle          FetchTask
    │  transformed by
    ▼
ArticleScrapedEvent ──► InMemoryEventBus
    │
    ▼  (ProcessScrapedArticleUseCase)
Article (DB)  ◄── deduplicated via UrlHash
    │
    └── ArxivMetadata (DB, optional)
```

---

## Domain Entities

### ScrapeJob
Produced by a scraper's `discover()`. Represents one pending fetch unit.

| Field | Type | Notes |
|-------|------|-------|
| `url` | str | Article URL to fetch |
| `source` | str | Human-readable source name (e.g. "TechCrunch") |
| `source_type` | str | `"rss"` \| `"arxiv"` \| `"blog"` |
| `topic_id` | UUID \| None | Associates article with a topic |
| `prompt_override` | str \| None | Custom LLM prompt for this source |
| `metadata` | dict | Raw metadata: title, description, author, published, arxiv_id, etc. |

### ArxivMetadata
Persisted alongside `Article` for arXiv papers. Optional — only created when `source == "arxiv"`.

| Field | Type | Notes |
|-------|------|-------|
| `article_id` | UUID | FK to Article |
| `arxiv_id` | str \| None | e.g. `"2401.12345"` |
| `authors` | list[str] | Author names |
| `pdf_available` | bool | Whether PDF was successfully fetched |
| `sections` | dict | PDF section map (heading → text) |

---

## Value Objects

### ScrapedArticle
Result of a successful `fetch()`. Immutable; not persisted directly.

| Field | Type | Notes |
|-------|------|-------|
| `url` | str | Canonical article URL |
| `title` | str | Article title |
| `content` | str | Sanitised plain text (may be truncated) |
| `source` | str | Source name |
| `topic_id` | UUID \| None | |
| `published_at` | datetime \| None | |
| `authors` | list[str] | |
| `extra` | dict | Source-specific metadata passed through to event |

### UrlHash
Deterministic deduplication key.

| Field | Type | Notes |
|-------|------|-------|
| `value` | str | SHA-256 hex of normalised URL |

**Normalisation rules**: lowercase, strip trailing slash, remove fragment (`#…`).

---

## Application Events

### ArticleScrapedEvent
Published to `InMemoryEventBus` after a successful fetch. Consumed by `ArticleScrapedHandler`
which invokes `ProcessScrapedArticleUseCase`.

| Field | Type | Source |
|-------|------|--------|
| `url` | str | `ScrapedArticle.url` |
| `title` | str | `ScrapedArticle.title` |
| `content` | str | `ScrapedArticle.content` |
| `source` | str | `ScrapedArticle.source` |
| `topic_id` | UUID \| None | `ScrapedArticle.topic_id` |
| `published_at` | datetime \| None | |
| `metadata` | dict | `ScrapedArticle.extra` |

---

## Infrastructure Configuration Entities

### ScraperSetting (DB)
Loaded at pipeline start from DB via `ScraperSettingRepository`. Drives `ScraperFactory`.

| Field | Type | Notes |
|-------|------|-------|
| `source` | str | Unique source name |
| `source_type` | str | `"rss"` \| `"arxiv"` \| `"blog"` |
| `url` | str | Feed URL / API endpoint / blog listing URL |
| `keywords` | list[str] \| None | Keyword filter; None = use defaults |
| `topic_id` | UUID \| None | |
| `prompt_override` | str \| None | |
| `enabled` | bool | If False, skipped at pipeline start |
| `selectors` | dict \| None | CSS selectors for blog sources |
| `fetch_pdf` | bool | ArXiv only: whether to extract PDF |

---

## Deduplication State Machine

```
URL encountered during run
        │
        ▼
DedupService.find_existing(url)
        │
   ┌────┴────┐
   │         │
  None    Article found
   │         │
   ▼         ▼
 NEW    needs_analysis(article)?
             │
        ┌────┴────┐
        │         │
       True     False
        │         │
        ▼         ▼
  DUPLICATE_   DUPLICATE
  NEEDS_       (skip)
  ANALYSIS
```

**Outcomes** (`ArticleOutcome` enum):
- `NEW` — stored and forwarded for analysis
- `DUPLICATE_NEEDS_ANALYSIS` — not re-stored; forwarded for analysis
- `DUPLICATE` — silently dropped
- `FAILED` — storage error; recorded in failed task log
