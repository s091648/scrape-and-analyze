# Data Model: Semantic Scholar Scraper

**Feature**: 011-semantic-scholar-scraper | **Date**: 2026-06-04

## 概覽

本功能**不新增任何資料庫表格或欄位**。所有新型別均儲存於既有欄位（JSONB 或 varchar）。

---

## 新增 Python 型別

### `SemanticScholarConfig`（Pydantic BaseModel）

位置：`shared/selector_config.py`

| 欄位 | 型別 | 預設值 | 說明 |
|------|------|--------|------|
| `type` | `Literal["semantic_scholar"]` | `"semantic_scholar"` | discriminator |
| `max_results` | `int` | `20` | 每次最多取幾篇 |
| `days_back` | `int` | `7` | 只取最近 N 天的論文 |

儲存於 `scraper_settings.selector_config` JSONB 欄位，例：
```json
{"type": "semantic_scholar", "max_results": 20, "days_back": 7}
```

---

### `SemanticScholarKeyword`（Pydantic BaseModel）

位置：`src/modules/collection/domain/value_objects/scraper_keyword.py`

| 欄位 | 型別 | 說明 |
|------|------|------|
| `type` | `Literal["semantic_scholar_keyword"]` | discriminator |
| `keyword` | `str` | 搜尋關鍵字（如 `"digital twin"`, `"reinforcement learning"`）|

存於 `scraper_keywords` 表，`keyword_type = "semantic_scholar_keyword"`。

---

### `SemanticScholarEntry`（內部 dataclass）

位置：`src/infrastructure/collection/clients/semantic_scholar_client.py`

| 欄位 | 型別 | 說明 |
|------|------|------|
| `paper_id` | `str` | S2 內部 paper ID |
| `url` | `str` | 正規化後的 URL（ArXiv URL 優先） |
| `title` | `str` | 論文標題 |
| `abstract` | `str` | 摘要 |
| `authors` | `List[str]` | 作者姓名清單 |
| `publication_date` | `Optional[str]` | ISO date string，e.g. `"2025-01-15"` |
| `open_access_pdf_url` | `Optional[str]` | 開放取用 PDF 連結 |
| `doi` | `Optional[str]` | DOI |
| `arxiv_id` | `Optional[str]` | ArXiv ID |
| `citation_count` | `int` | 引用數 |
| `is_open_access` | `bool` | 是否開放取用 |

此為 `SemanticScholarClient` 內部使用的中間型別，不寫入 DB。

---

## 修改既有型別

### `SelectorConfig` union（`shared/selector_config.py`）

新增 `SemanticScholarConfig` 至 discriminated union：

```python
# Before
SelectorConfig = Annotated[
    Union[RssConfig, BlogConfig, ArxivConfig],
    Field(discriminator="type"),
]

# After
SelectorConfig = Annotated[
    Union[RssConfig, BlogConfig, ArxivConfig, SemanticScholarConfig],
    Field(discriminator="type"),
]
```

`build_selector_config()` 新增 `"semantic_scholar"` 分支：
```python
if source_type == "semantic_scholar":
    return SemanticScholarConfig(
        max_results=raw.get("max_results", 20),
        days_back=raw.get("days_back", 7),
    )
```

---

### `ScraperKeywordVO` union（`scraper_keyword.py`）

新增 `SemanticScholarKeyword` 至 union，`build_scraper_keyword()` 新增 `"semantic_scholar_keyword"` 分支。

---

### `VALID_KEYWORD_TYPES` enum（`shared/enums/scraper_keyword.py`）

```python
# Before
VALID_KEYWORD_TYPES: frozenset[str] = frozenset({"rss", "arxiv_keyword", "arxiv_category"})

# After
VALID_KEYWORD_TYPES: frozenset[str] = frozenset({
    "rss",
    "arxiv_keyword",    # 保留向下相容，系統層不再主動使用
    "arxiv_category",
    "semantic_scholar_keyword",
})
```

---

### `Article.get_analysis_content()`（`src/shared/domain/entities/article.py`）

```python
# Before
if self.source == "arxiv":
    ...

# After
if self.source in ("arxiv", "semantic_scholar"):
    ...
```

---

## ScrapeJob metadata（semantic_scholar）

`SemanticScholarScraper.discover()` 產出的 `ScrapeJob.metadata` 欄位：

```python
{
    "paper_id": str,           # S2 paper ID
    "title": str,
    "abstract": str,
    "open_access_pdf_url": Optional[str],
    "doi": Optional[str],
    "arxiv_id": Optional[str],
    "citation_count": int,
    "is_open_access": bool,
    "authors": List[str],
    "published": Optional[str],  # ISO date string
}
```

## ScrapedArticle extra（semantic_scholar）

`SemanticScholarScraper.fetch()` 產出的 `ScrapedArticle.extra` 欄位：

```python
{
    "paper_id": str,
    "abstract": str,
    "doi": Optional[str],
    "arxiv_id": Optional[str],
    "citation_count": int,
    "is_open_access": bool,
    "pdf_available": bool,
    "sections": Dict[str, str],  # 空 dict 若無 PDF
}
```
