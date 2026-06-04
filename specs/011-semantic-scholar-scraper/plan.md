# Implementation Plan: Semantic Scholar Scraper

**Branch**: `feat/semantic_scholar` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-semantic-scholar-scraper/spec.md`

## Summary

新增 Semantic Scholar 作為第四種 scraper 來源，以解決 ArXiv rate limit 問題並擴大論文涵蓋範圍。Semantic Scholar 提供免費的 REST API，支援 keyword 搜尋 title + abstract，可取得開放取用 PDF URL、DOI、ArXiv ID 等豐富 metadata。

技術方案：以 ArXiv scraper 為參考範本，新增 `SemanticScholarClient`（HTTP adapter）+ `SemanticScholarScraper`（discover + fetch），整合至現有 `ConcreteScraperFactory`。同步將 ArXiv 限縮為只用 category 訂閱（移除 keyword 搜尋），在 backend 共用 enum 和前端 UI 一同更新。無需 Alembic migration（所有新設定儲存於既有 JSONB/varchar 欄位）。

## Technical Context

**Language/Version**: Python 3.11（scraper/backend）、TypeScript + React 19（frontend）

**Primary Dependencies**: requests（HTTP）、pydantic（schema）、SQLAlchemy 2.x（ORM）；前端：Next.js 16、Shadcn/UI、Tailwind CSS v4

**Storage**: PostgreSQL 15（既有）；`scraper_settings.selector_config` JSONB 欄位新增 `SemanticScholarConfig`；`scraper_keywords.keyword_type` varchar 新增 `semantic_scholar_keyword` — 無 DB schema 變更

**Testing**: pytest（Python unit + integration）、Vitest（前端 unit）、Playwright（前端 E2E）

**Target Platform**: Linux server（Docker container），`src/` scraper service

**Project Type**: Web service + scheduled scraper pipeline

**Performance Goals**: 單次 Semantic Scholar scrape（20 篇）< 60 秒（不含 PDF 下載）

**Constraints**: Semantic Scholar 免費層 1 req/sec；rate limit 錯誤需 warn-and-skip（不中斷 pipeline）；開放取用 PDF 下載失敗需退回 abstract

**Scale/Scope**: 與既有 pipeline 規模相同（小規模、排程執行）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD | ✅ Pass | `SemanticScholarClient` → `infrastructure/collection/clients/`；`SemanticScholarScraper` → `infrastructure/collection/scrapers/`；無 domain logic 外漏 |
| II. Atomic Frontend | ✅ Pass | `SemanticScholarKeywordManager` → `components/features/scraper/`；附帶 `.stories.tsx` |
| III. Test Discipline | ✅ Pass | 需包含 scraper unit tests（`src/tests/unit/`）+ frontend unit tests（`frontend/tests/unit/`）|
| IV. Docker-First | ✅ Pass | 無需改動 Docker 設定；既有服務架構沿用 |
| V. CI-Only Deployment | ✅ Pass | 無 DB schema 變更，無需 Alembic migration；無需 rollback job 修改 |
| VI. Observability | ✅ Pass | `SemanticScholarClient` + `SemanticScholarScraper` MUST 使用 structlog |
| VII. Code Style | ✅ Pass | 沿用 PEP 8、Pydantic schema、i18n provider |

**Post-design re-check**: 所有原則通過，無違規需記錄於 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/011-semantic-scholar-scraper/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── semantic-scholar-api.md
│   └── keyword-type-enum.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
# Backend — 新增檔案
src/infrastructure/collection/clients/
└── semantic_scholar_client.py    ← 新增

src/infrastructure/collection/scrapers/
└── semantic_scholar_scraper.py   ← 新增

# Backend — 修改檔案
shared/selector_config.py         ← 新增 SemanticScholarConfig
shared/enums/scraper_keyword.py   ← 新增 "semantic_scholar_keyword"
src/modules/collection/domain/value_objects/scraper_keyword.py  ← 新增 SemanticScholarKeyword VO
src/infrastructure/collection/scrapers/scraper_factory.py       ← 新增 SS 分支；ArXiv 移除 keywords
src/infrastructure/collection/scrapers/__init__.py              ← export SemanticScholarScraper
src/infrastructure/collection/clients/__init__.py               ← export SemanticScholarClient
src/shared/domain/entities/article.py                          ← 更新 get_analysis_content()

# Backend — 測試（新增）
src/tests/unit/infrastructure/collection/clients/
└── test_semantic_scholar_client.py

src/tests/unit/infrastructure/collection/scrapers/
└── test_semantic_scholar_scraper.py

# Frontend — 新增檔案
frontend/components/features/scraper/
├── semantic-scholar-keyword-manager.tsx
└── semantic-scholar-keyword-manager.stories.tsx

# Frontend — 修改檔案
frontend/app/admin/scraper-settings/page.tsx  ← 新增 SS 卡片；移除 ArXiv keyword UI
frontend/i18n/en.json                         ← 新增 SS 相關字串
frontend/i18n/zh-TW.json                      ← 新增 SS 相關字串（繁體中文）

# Frontend — 測試（新增）
frontend/tests/unit/components/features/scraper/
└── semantic-scholar-keyword-manager.test.tsx
```

**Structure Decision**: Web application（Option 2）— scraper/backend 共用 `shared/`，前後端各自測試目錄，與既有架構完全一致。
