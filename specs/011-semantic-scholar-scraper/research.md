# Research: Semantic Scholar Scraper

**Feature**: 011-semantic-scholar-scraper | **Date**: 2026-06-04

## 1. Semantic Scholar API

**Decision**: 使用 Semantic Scholar Academic Graph API 的 Paper Search 端點。

**Endpoint**: `GET https://api.semanticscholar.org/graph/v1/paper/search`

**Key parameters**:

| 參數 | 說明 |
|------|------|
| `query` | 關鍵字搜尋（比對 title + abstract） |
| `fields` | 逗號分隔的欄位清單 |
| `limit` | 每頁筆數（max 100） |
| `offset` | 分頁偏移 |
| `sort` | `PublicationDate:desc`（最新優先） |
| `publicationDateOrYear` | 年份範圍，e.g. `2025-2026` |

**Request fields 選定**:
```
paperId,title,abstract,authors,publicationDate,year,
openAccessPdf,externalIds,isOpenAccess,citationCount
```

**Rationale**: 官方 REST API，免費且文件完整。不使用第三方包裝或 RSS（無 RSS feed）。

---

## 2. Rate Limiting 策略

**Decision**: 有 API key → 設定 `x-api-key` header；無 key → 免費層（1 req/sec）。HTTP 429 → warn-and-return-empty，不 raise 中斷 pipeline。

**Implementation**: `SEMANTIC_SCHOLAR_API_KEY` env var 設定 API key。

---

## 3. URL 正規化（去重策略）

**Decision**: 若論文有 `externalIds.ArXiv`，使用 `https://arxiv.org/abs/{arxiv_id}` 作為正規 URL；否則使用 `https://www.semanticscholar.org/paper/{paperId}`。

**Rationale**: 與 ArXiv scraper 抓到同一篇論文時，`UrlHash` dedup 可自動去重。

---

## 4. PDF 取得策略

**Decision**: Option B — 有 `openAccessPdf.url` 時下載並解析全文；無 PDF 時退回 abstract；任何 PDF 失敗都退回 abstract，不中斷流程。

**Implementation**: 在 `SemanticScholarScraper.fetch()` 中複用 `PdfParser`，與 ArxivScraper 完全相同的邏輯。

---

## 5. `get_analysis_content()` 更新

**Decision**: 將條件從 `self.source == "arxiv"` 改為 `self.source in ("arxiv", "semantic_scholar")`。semantic_scholar 的 `extra["sections"]` 結構與 arxiv 相同，可共用邏輯。

---

## 6. ArXiv Keyword 限縮

**Decision**: 在 `ConcreteScraperFactory` 的 ArXiv 分支，不傳入 `keywords`（`keywords=None`）。同步移除前端 ArXiv keyword 管理 UI。現有 `arxiv_keyword` DB 資料保留，系統層忽略。

**Rationale**: ArXiv keyword 搜尋是 rate limit 主因。category 訂閱量小，不會觸發 429。

---

## 7. 前端元件設計

**Decision**: `SemanticScholarKeywordManager` 為純關鍵字管理器，平行 ArXiv 的 keyword manager 設計。Scraper Settings 頁面新增 "Semantic Scholar" AccordionSection，採 singleton 模式（每個 topic 最多一個）。

---

## 8. 無需 Alembic Migration

**Decision**: 本功能不需要任何 DB schema 變更。`selector_config` 欄位為 JSONB，`source_type` 和 `keyword_type` 欄位為 varchar，無 CHECK constraint。只需更新應用層 enum。
