# Implementation Plan: Semantic Scholar + OpenAlex Scraper

**Branch**: `feat/semantic_scholar` | **Date**: 2026-06-04 | **Updated**: 2026-06-05 (rev 2) | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/011-semantic-scholar-scraper/spec.md`

## Summary

新增 Semantic Scholar 與 OpenAlex 作為第四、五種 scraper 來源，以解決 ArXiv rate limit 問題並擴大論文涵蓋範圍。

**Semantic Scholar**：已實作（`SemanticScholarClient` + `SemanticScholarScraper`）。實際測試發現免費 API 無法個人申請 key（需機構帳號），且首次執行即 HTTP 429。保留實作供日後有 key 時使用，以 OpenAlex 作為主要免費來源。

**OpenAlex**：完全免費，無需 API key。透過 User-Agent 帶 `mailto:` 進入 polite pool（10 req/sec）。以相同架構新增 `OpenAlexClient` + `OpenAlexScraper`，差異在於 abstract 需從 inverted index 還原為純文字。

技術方案：以 Semantic Scholar scraper 為範本新增 OpenAlex 實作，整合至 `ConcreteScraperFactory`，前端新增 OpenAlex AccordionSection。無需 Alembic migration（所有新設定儲存於既有 JSONB/varchar 欄位）。

## Technical Context

**Language/Version**: Python 3.11（scraper/backend）、TypeScript + React 19（frontend）

**Primary Dependencies**: requests（HTTP）、pydantic（schema）、SQLAlchemy 2.x（ORM）；前端：Next.js 16、Shadcn/UI、Tailwind CSS v4

**Storage**: PostgreSQL 15（既有）；`scraper_settings.selector_config` JSONB 欄位新增 `SemanticScholarConfig` + `OpenAlexConfig`；`scraper_keywords.keyword_type` varchar 新增 `semantic_scholar_keyword` + `openalex_keyword` — 無 DB schema 變更

**Testing**: pytest（Python unit + integration）、Vitest（前端 unit）、Playwright（前端 E2E）

**Target Platform**: Linux server（Docker container），`src/` scraper service

**Project Type**: Web service + scheduled scraper pipeline

**Performance Goals**: 單次 Semantic Scholar scrape（20 篇）< 60 秒（不含 PDF 下載）

**Constraints**: Semantic Scholar 免費層 IP 配額極低（首次執行即 429，需機構帳號才能申請 key）；OpenAlex polite pool 10 req/sec，rate limiter 設定 5 RPM；兩者 rate limit 錯誤均需 warn-and-skip（不中斷 pipeline）；PDF 下載失敗需退回 abstract；HTTP client 不得在 `Accept-Encoding` 中宣告 `br`（Brotli），因 `requests` 套件未安裝 brotli 解碼器

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
├── semantic_scholar_client.py    ← 新增（已完成）
└── openalex_client.py            ← 新增（已完成）

src/infrastructure/collection/scrapers/
├── semantic_scholar_scraper.py   ← 新增（已完成）
└── openalex_scraper.py           ← 新增（已完成）

# Backend — 修改檔案
shared/selector_config.py         ← 新增 SemanticScholarConfig + OpenAlexConfig（已完成）
shared/enums/scraper_keyword.py   ← 新增 "semantic_scholar_keyword" + "openalex_keyword"（已完成）
src/modules/collection/domain/value_objects/scraper_keyword.py  ← 新增 SemanticScholarKeyword + OpenAlexKeyword VO（已完成）
src/infrastructure/collection/scrapers/scraper_factory.py       ← 新增 SS + OA 分支；ArXiv 移除 keywords（已完成）
src/infrastructure/collection/scrapers/__init__.py              ← export SemanticScholarScraper + OpenAlexScraper（已完成）
src/infrastructure/collection/clients/__init__.py               ← export SemanticScholarClient + OpenAlexClient（已完成）
src/infrastructure/shared/http/rate_limiter.py                  ← 新增 api.semanticscholar.org + api.openalex.org（已完成）
src/shared/domain/entities/article.py                          ← 更新 get_analysis_content()（已完成）
src/infrastructure/collection/collection_pipeline.py           ← 新增 SS/OA host routing（已完成）
src/infrastructure/shared/http/user_agent.py                   ← 移除 Accept-Encoding: br（已完成）
backend/schemas/scraper_setting.py                             ← Literal 新增 semantic_scholar + openalex（已完成）
backend/routers/articles.py                                    ← 新增 via_source/original_source 欄位 + aggregator filter（已完成）

# Backend — 測試（新增）
src/tests/unit/infrastructure/collection/clients/
├── test_semantic_scholar_client.py（已完成）
└── test_openalex_client.py（待補）

src/tests/unit/infrastructure/collection/scrapers/
├── test_semantic_scholar_scraper.py（已完成）
└── test_openalex_scraper.py（待補）

# Frontend — 新增檔案
frontend/components/features/scraper/
├── semantic-scholar-keyword-manager.tsx（已完成）
└── openalex-keyword-manager.tsx（已完成）

# Frontend — 修改檔案
frontend/app/admin/scraper-settings/page.tsx        ← 新增 SS + OA 卡片；移除 ArXiv keyword UI；合併 Aggregator accordion + type dialog（已完成）
frontend/app/home-page-content.tsx                  ← 新增 aggregators 傳遞（已完成）
frontend/lib/providers/locales/en.json              ← 新增 SS + OA + aggregator + filterBar 相關字串（已完成）
frontend/lib/providers/locales/zh-TW.json           ← 新增 SS + OA + aggregator + filterBar 相關字串（已完成）
frontend/lib/api/scraper-settings.ts                ← source_type union 補上 semantic_scholar + openalex（已完成）
frontend/lib/api/articles.ts                        ← 新增 via_source / original_source / aggregator 欄位（已完成）
frontend/lib/api/graph.ts                           ← GraphFilters 新增 aggregator（已完成）
frontend/hooks/use-pagination.ts                    ← 新增 aggregators URL state（已完成）
frontend/components/features/articles/filter-bar.tsx          ← 新增 Aggregator filter（已完成）
frontend/components/features/articles/article-card.tsx        ← 顯示 original_source + via_source badge（已完成）
frontend/components/features/articles/article-detail-dialog.tsx ← 顯示 original_source + via_source badge（已完成）
frontend/components/features/articles/source-utils.ts         ← 新增共用工具（deriveDisplaySource, formatViaSource）（已完成）
frontend/components/features/graph/knowledge-graph.tsx        ← FilterBar 新增 aggregators prop（已完成）
frontend/components/features/scraper/scraper-source-card.tsx  ← source_type union 補上 semantic_scholar + openalex（已完成）

# Frontend — 測試（新增）
frontend/tests/unit/components/features/scraper/
├── semantic-scholar-keyword-manager.test.tsx（已完成）
└── openalex-keyword-manager.test.tsx（待補）
```

**Structure Decision**: Web application（Option 2）— scraper/backend 共用 `shared/`，前後端各自測試目錄，與既有架構完全一致。
