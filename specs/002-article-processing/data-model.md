# Data Model: Article Processing

**Feature**: [Article Processing](spec.md)
**Date**: 2026-05-29

## Entities

### Article

Core record representing a scraped piece of content.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `url` | str | NOT NULL | Original URL |
| `url_hash` | str | NOT NULL, UNIQUE, 64 chars | SHA-256 of URL; primary dedup key |
| `source` | str | NOT NULL | `"rss"`, `"arxiv"`, `"blog"` |
| `title` | str | NOT NULL | |
| `content` | str | NOT NULL | Full article text |
| `published_at` | datetime | nullable | From feed/scraper |
| `scraped_at` | datetime | nullable | Set at persistence time |
| `topic_id` | UUID | nullable, FK → Topic | |
| `metadata` | dict | NOT NULL, default `{}` | Arbitrary source metadata |

**Dedup key**: `url_hash` (unique constraint at DB level).

**State transitions**:
- Created → exists without Analysis → `needs_analysis() = True`
- Created → Analysis saved → `needs_analysis() = False`

---

### UrlHash

Value object. Not persisted directly — its `.value` is stored as `Article.url_hash`.

| Field | Type | Constraints |
|-------|------|-------------|
| `value` | str | 64-char hex string (SHA-256 digest) |

**Invariants**:
- Cannot be created from an empty URL.
- Must be exactly 64 hex characters.

---

### ArticleOutcome

Enum. Not persisted — returned from `ProcessScrapedArticleUseCase.execute()`.

| Value | Meaning |
|-------|---------|
| `NEW` | Article was just created and saved |
| `DUPLICATE` | Article exists and already has an Analysis |
| `DUPLICATE_NEEDS_ANALYSIS` | Article exists but has no Analysis |
| `FAILED` | Save attempt raised an exception |

---

### ArxivMetadata

Supplementary record for ArXiv-sourced articles only.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `article_id` | UUID | FK → Article, NOT NULL | |
| `arxiv_id` | str | nullable | e.g. `"2501.12345"` |
| `authors` | list[str] | NOT NULL, default `[]` | |
| `pdf_available` | bool | NOT NULL, default `False` | |
| `sections` | dict | NOT NULL, default `{}` | Section name → text body |

**Lifecycle**: Created once when a NEW ArXiv article is saved. Read back when a `DUPLICATE_NEEDS_ANALYSIS` ArXiv article is re-queued (sections merged into `article.metadata["sections"]`).

---

### ArticleProcessedEvent

Application event. Not persisted — published on the in-memory event bus.

| Field | Type | Notes |
|-------|------|-------|
| `article` | Article | The newly saved or re-queued Article |

**Published when**: `ArticleOutcome` is `NEW` or `DUPLICATE_NEEDS_ANALYSIS`.
**Not published when**: `ArticleOutcome` is `DUPLICATE` or `FAILED`.

## Relationships

```
Topic 1──────────────────────────────────────── * Article
                                                   |
                                                   │ 0..1
                                                   ▼
                                              ArxivMetadata

Article 1──────────────────────────────────── 0..1 Analysis
         (checked by DedupService.needs_analysis)
```
