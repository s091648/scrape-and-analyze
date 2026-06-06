# Contract: Scraper Keyword Types

**Type**: Internal shared enum（backend API validation）
**Location**: `shared/enums/scraper_keyword.py` | **Date**: 2026-06-04

## `VALID_KEYWORD_TYPES`

Controls which `keyword_type` values are accepted by `POST /scraper-keywords`.

```python
VALID_KEYWORD_TYPES: frozenset[str] = frozenset({
    "rss",
    "arxiv_keyword",             # Legacy: system ignores at scrape time
    "arxiv_category",
    "semantic_scholar_keyword",  # New in this feature
})
```

## Usage

### Backend validation（`backend/routers/scraper_keywords.py`）

```python
@field_validator("keyword_type")
@classmethod
def _check_type(cls, v: str) -> str:
    if v not in VALID_KEYWORD_TYPES:
        raise ValueError(f"keyword_type must be one of {sorted(VALID_KEYWORD_TYPES)}")
    return v
```

### Scraper factory mapping

| `keyword_type` | Used by | Notes |
|----------------|---------|-------|
| `rss` | `RssScraper` | Regex filter on RSS entry titles |
| `arxiv_keyword` | ~~`ArxivScraper`~~ | Stored but ignored at scrape time（deprecated） |
| `arxiv_category` | `ArxivScraper` | Category code, e.g. `cs.LG` |
| `semantic_scholar_keyword` | `SemanticScholarScraper` | Free-text search keyword |

## Frontend keyword_type per source

| Source type | Keyword types available in UI |
|-------------|-------------------------------|
| `rss` | `rss` |
| `arxiv` | `arxiv_category` only（`arxiv_keyword` UI removed） |
| `semantic_scholar` | `semantic_scholar_keyword` |
| `blog` | None |
