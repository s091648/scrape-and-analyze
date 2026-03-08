# Content Parser Layer + arXiv PDF Full Text

**Date:** 2026-03-09
**Status:** Approved

## Context

The scrapers were moved from `src/scrapers/` into `src/scrapers/scrapers/`, breaking all existing imports in tests and `main.py`. Simultaneously, we want to:

1. Separate content parsing logic from scraper orchestration
2. Add a PDF parser for arXiv full text extraction

## Goals

- Fix broken imports across tests and `main.py`
- Extract reusable HTML content parsing into `content_parsers/`
- Store arXiv PDF full text in `article.content` while preserving the original abstract in `metadata_`
- At analysis time, send only relevant sections to the LLM (fallback to original abstract if extraction fails)
- No database schema changes required

## Constraints

- Gemini free tier: 5 RPM, 250K TPM, **20 RPD** — the binding constraint is RPD
- Must not increase per-article token cost unless section extraction succeeds
- Existing `LeakyBucketStrategy` handles rate limiting; content truncation is a complementary upstream guard

---

## Architecture

### Directory Structure

```
src/scrapers/
├── __init__.py
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py
│   ├── arxiv_scraper.py
│   ├── rss_scraper.py
│   └── blog_scraper.py
└── content_parsers/
    ├── __init__.py
    ├── base_parser.py      # BaseContentParser ABC
    ├── html_parser.py      # HtmlArticleParser (RSS + Blog)
    └── pdf_parser.py       # PdfParser (arXiv)
```

### BaseContentParser

```python
class BaseContentParser(ABC):
    @abstractmethod
    def parse(self, ...) -> str:
        """Return full content string."""

    def prepare_for_analysis(self, content: str, **kwargs) -> str:
        """Return LLM-ready excerpt. Default: return as-is."""
        return content
```

---

## Component Designs

### HtmlArticleParser (`html_parser.py`)

Consolidates the duplicated HTML body extraction logic currently in:
- `RssScraper._fetch_full_content()` — HTTP fetch + selector-based extraction
- `BlogScraper._extract_article()` — selector-based extraction

```python
class HtmlArticleParser(BaseContentParser):
    FALLBACK_SELECTORS = [
        'article', 'main',
        '[class*="article-body"]', '[class*="post-content"]',
        '[class*="entry-content"]', '[class*="content-body"]',
    ]

    def parse(self, html: str, selectors: list[str] | None = None) -> str:
        """Extract article body from HTML string using CSS selectors."""

    def fetch_and_parse(self, url: str, fallback: str = '') -> str:
        """HTTP GET + parse. Returns fallback on failure."""
```

`RssScraper` and `BlogScraper` delegate to this parser instead of containing the logic inline.

### PdfParser (`pdf_parser.py`)

```python
class PdfParser(BaseContentParser):
    TARGET_HEADINGS = ['abstract', 'introduction', 'method', 'conclusion', 'summary']
    MAX_CHARS = 15_000  # ~4k tokens, safe within 20 RPD budget

    def parse(self, pdf_url: str) -> str:
        """Download PDF from URL, return full extracted text."""

    def extract_sections(self, text: str) -> dict[str, str]:
        """
        Heuristic regex extraction of target sections.
        Returns dict of {section_name: content}.
        """

    def prepare_for_analysis(self, content: str, fallback: str = '') -> str:
        """
        Returns LLM-ready text:
        - If >= 2 target sections found → concatenated sections (capped at MAX_CHARS)
        - Otherwise → fallback string (original arXiv abstract)
        """
```

PDF library: `pymupdf` (fitz) — reliable text extraction, handles most arXiv PDFs well.
Add to `requirements.txt`: `pymupdf>=1.24`.

---

## Data Flow

### Scraping Phase (ArxivScraper)

```
arXiv API → entry with abstract + pdf_link
    ↓
PdfParser.parse(pdf_url)
    ├── success → content = full_pdf_text
    │             metadata['abstract'] = api_summary
    │             metadata['pdf_available'] = True
    └── failure → content = api_summary   (existing behaviour)
                  metadata['pdf_available'] = False
    ↓
ScrapedArticle(content=..., metadata=...)
    ↓
DB: article.content = full text (or summary on failure)
    article.metadata_ = {authors, arxiv_id, abstract, pdf_available}
```

### Analysis Phase

```python
# src/scrapers/content_parsers/__init__.py (or src/utils/content_prep.py)

def prepare_content_for_analysis(article) -> str:
    if article.source == 'arxiv':
        parser = PdfParser()
        sections = parser.extract_sections(article.content)
        if len(sections) >= 2:
            return "\n\n".join(sections.values())
        # Fallback: original abstract (minimal tokens, existing behaviour)
        return (article.metadata_ or {}).get('abstract', article.content[:2000])
    return article.content
```

`analyze_article()` in `main.py` changes one line:

```python
# Before
result = analyzer.analyze(article.content, prompt)

# After
from src.scrapers.content_parsers import prepare_content_for_analysis
llm_content = prepare_content_for_analysis(article)
result = analyzer.analyze(llm_content, prompt)
```

---

## Import Fix Map

All broken imports must be updated:

| File | Old import | New import |
|------|-----------|-----------|
| `tests/unit/test_scrapers.py` | `src.scrapers.base` | `src.scrapers.scrapers.base_scraper` |
| `tests/unit/test_rss_scraper.py` | `src.scrapers.rss_scraper` | `src.scrapers.scrapers.rss_scraper` |
| `tests/unit/test_blog_scraper.py` | `src.scrapers.blog_scraper` | `src.scrapers.scrapers.blog_scraper` |
| `tests/unit/test_arxiv_scraper.py` | `src.scrapers.arxiv_scraper` | `src.scrapers.scrapers.arxiv_scraper` |
| `src/main.py:22-24` | same old paths | same new paths |

---

## Token Budget Summary

| Scenario | Chars sent to LLM | Approx tokens |
|----------|------------------|---------------|
| Section extraction success | ~5k–10k | ~1.5k–3k |
| Section extraction fails | abstract only (~1k chars) | ~300 |
| Non-arxiv articles | full scraped content | varies |

With 20 RPD and ~2k avg tokens/request: well within 250K TPM.

---

## Testing Strategy

- `test_html_parser.py` — unit tests for `HtmlArticleParser.parse()` and `fetch_and_parse()`
- `test_pdf_parser.py` — unit tests for `PdfParser.extract_sections()` with fixture text; mock HTTP for `parse()`
- `test_arxiv_scraper.py` — update existing tests to use new import path; add test for PDF fallback path
- `test_rss_scraper.py`, `test_blog_scraper.py` — update imports; verify delegation to `HtmlArticleParser`
- `test_main.py` — verify `prepare_content_for_analysis()` called before `analyzer.analyze()`

---

## Tasks

1. **Fix imports** — update all broken import paths in tests + `main.py`
2. **HtmlArticleParser** — extract HTML parsing logic from RSS + Blog scrapers; update scrapers to delegate
3. **PdfParser** — implement `parse()` + `extract_sections()` + `prepare_for_analysis()`; add `pymupdf` to `requirements.txt`
4. **ArxivScraper** — attempt PDF download; store full text in `content`, abstract in `metadata['abstract']`
5. **prepare_content_for_analysis()** — add utility function; wire into `analyze_article()` in `main.py`
6. **Tests** — write/update tests for all changed components; verify passing in Docker
