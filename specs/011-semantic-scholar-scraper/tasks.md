# Tasks: Semantic Scholar + OpenAlex Scraper

**Input**: Design documents from `specs/011-semantic-scholar-scraper/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Updated**: 2026-06-05 (rev 2) — 新增 Phase 9~11（Bug Fixes、Article Source Attribution、Aggregator Filter）

**Tests**: 依 Constitution §III，本 tasks.md 包含強制測試 phase。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel（不同檔案，無相依）
- **[Story]**: 對應 spec.md 的 user story（US1, US2, US3）

---

## Phase 1: Setup

**Purpose**: 確認既有依賴，無需新增 Python 套件

- [x] T001 確認 `pyproject.toml` 中 `requests` 已存在（ArXiv client 已使用），無需新增依賴

---

## Phase 2: Foundational（Shared Type Definitions）

**Purpose**: 共用型別定義，US1/US2/US3 均依賴這些變更

**⚠️ CRITICAL**: 所有 User Story 均需此 Phase 完成後才可開始

- [x] T002 [P] 新增 `SemanticScholarConfig` 至 `shared/selector_config.py`：加入 `type: Literal["semantic_scholar"]`、`max_results: int = 20`、`days_back: int = 7` 欄位；更新 `SelectorConfig` union 與 `build_selector_config()` 函式新增 `"semantic_scholar"` 分支
- [x] T003 [P] 新增 `"semantic_scholar_keyword"` 至 `shared/enums/scraper_keyword.py` 的 `VALID_KEYWORD_TYPES` frozenset
- [x] T004 [P] 新增 `SemanticScholarKeyword` Pydantic model 至 `src/modules/collection/domain/value_objects/scraper_keyword.py`；更新 `ScraperKeywordVO` union 加入 `SemanticScholarKeyword`；更新 `build_scraper_keyword()` 加入 `"semantic_scholar_keyword"` 分支

**Checkpoint**: 共用型別就緒，後續 Phase 可開始 ✅

---

## Phase 3: User Story 1 — 設定 Semantic Scholar 來源並自動抓取論文（Priority: P1）🎯 MVP

**Goal**: 管理員可在 scraper-settings 頁面啟用 Semantic Scholar、設定 keyword、讓系統 discover 論文並寫入資料庫

**Independent Test**: 在 admin UI 啟用 Semantic Scholar + 加入 keyword，手動觸發 `make scrape SOURCE=semantic_scholar LIMIT=3`，確認資料庫出現 `source = 'semantic_scholar'` 的論文

### 後端實作（US1）

- [x] T005 [P] [US1] 建立 `SemanticScholarClient` 於 `src/infrastructure/collection/clients/semantic_scholar_client.py`；更新 `src/infrastructure/collection/clients/__init__.py` export
- [x] T006 [US1] 建立 `SemanticScholarScraper` 於 `src/infrastructure/collection/scrapers/semantic_scholar_scraper.py`；更新 `src/infrastructure/collection/scrapers/__init__.py` export
- [x] T007 [US1] 更新 `src/infrastructure/collection/scrapers/scraper_factory.py` 的 `ConcreteScraperFactory.create_for()`：加入 `SemanticScholarConfig` 分支

### 前端實作（US1）

- [x] T008 [P] [US1] 新增 Semantic Scholar 相關 i18n key 至 `frontend/lib/providers/locales/en.json` 與 `zh-TW.json`
- [x] T009 [P] [US1] 建立 `frontend/components/features/scraper/semantic-scholar-keyword-manager.tsx` 及 `.stories.tsx`
- [x] T010 [US1] 在 `frontend/app/admin/scraper-settings/page.tsx` 加入 `SemanticScholarSettingCard` 與 `AddSemanticScholarCard`
- [x] T011 [US1] 在 `frontend/app/admin/scraper-settings/page.tsx` 加入 Semantic Scholar AccordionSection 與 state management

### 測試（US1）

- [x] T012 [P] [US1] 撰寫 `src/tests/unit/infrastructure/collection/clients/test_semantic_scholar_client.py`（8 個測試）
- [x] T013 [P] [US1] 撰寫 `src/tests/unit/infrastructure/collection/scrapers/test_semantic_scholar_scraper.py`（discover 部分）
- [ ] T014 [P] [US1] 撰寫 `frontend/tests/unit/semantic-scholar-keyword-manager.test.tsx`

**Checkpoint**: US1 完整可測試 ✅

---

## Phase 4: User Story 2 — 開放取用論文取得全文供 LLM 分析（Priority: P2）

**Goal**: 有開放取用 PDF 的論文自動下載全文解析段落，無 PDF 退回 abstract，LLM 分析使用完整段落內容

**Independent Test**: 抓取一篇已知有開放取用 PDF 的論文，確認 LLM 分析結果使用段落全文而非純 abstract

### 後端實作（US2）

- [x] T015 [US2] 更新 `SemanticScholarScraper.fetch()` 於 `src/infrastructure/collection/scrapers/semantic_scholar_scraper.py`：加入 `PdfParser` PDF 下載與解析邏輯
- [x] T016 [US2] 更新 `src/shared/domain/entities/article.py` 的 `Article.get_analysis_content()`：將條件改為 `self.source in ("arxiv", "semantic_scholar")`

### 測試（US2）

- [x] T017 [P] [US2] 補充 `test_semantic_scholar_scraper.py` 的 fetch() 測試（PDF available、no PDF、PDF failure 三種情境）
- [x] T018 [P] [US2] 補充 `src/tests/unit/shared/domain/test_article.py`：測試 `get_analysis_content()` 對 `semantic_scholar` source 的行為

**Checkpoint**: US2 完整可測試 ✅

---

## Phase 5: User Story 3 — ArXiv 設定精簡為只使用分類訂閱（Priority: P3）

**Goal**: ArXiv scraper 系統層不再使用 keyword 查詢；前端 ArXiv 設定介面移除 keyword 管理區塊

**Independent Test**: 在 ArXiv 設定頁面確認 keyword 新增區塊消失；執行 ArXiv scrape 確認仍依 category 正常抓取

### 後端實作（US3）

- [x] T019 [US3] 更新 `src/infrastructure/collection/scrapers/scraper_factory.py` 的 ArXiv 分支：將 `keywords=None`（已在 T007 同步完成）

### 前端實作（US3）

- [x] T020 [US3] 更新 `frontend/app/admin/scraper-settings/page.tsx`：移除 ArXiv keyword 管理 UI（已完成）

### 測試（US3）

- [x] T021 [P] [US3] 補充 `src/tests/unit/infrastructure/collection/scrapers/test_arxiv_scraper.py`：新增 `test_build_query_no_keywords_with_categories`
- [x] T022 [P] [US3] 新增/補充 `src/tests/unit/infrastructure/collection/scrapers/test_scraper_factory.py`

**Checkpoint**: US3 完整可測試 ✅

---

## Phase 6: Semantic Scholar Bug Fixes（2026-06-05 補充）

**Background**: 實作後發現的問題修正

- [x] T026 [P] 修正 `backend/schemas/scraper_setting.py` `ScraperSettingCreate.source_type` Literal 加入 `"semantic_scholar"`（修正 422 錯誤）
- [x] T027 [P] 修正 `models/types.py` `SelectorConfigColumn.process_bind_param`：改為對所有 `BaseModel` 呼叫 `model_dump()`（修正 500 序列化錯誤）
- [x] T028 [P] 修正 `backend/schemas/scraper_setting.py` `ScraperSettingOut` 加入 `field_validator` 將 Pydantic 物件轉 dict（修正 ResponseValidationError）
- [x] T029 [P] 修正 `src/infrastructure/persistence/collection/scraper_setting_repo_impl.py` `isinstance` check 加入 `SemanticScholarConfig`（修正 AttributeError: 'SemanticScholarConfig' object has no attribute 'get'）
- [x] T030 [P] 修正 `src/infrastructure/shared/http/rate_limiter.py` 新增 `api.semanticscholar.org: 1.0 RPM`（降低 429 頻率）
- [x] T031 [P] 修正 `frontend/app/admin/scraper-settings/page.tsx` `handleActivateArxiv` / `handleActivateSemanticScholar` 改為 `refreshKeywords()` 後 fetch，解決 keyword 顯示不全問題
- [x] T032 [P] 修正 `AddSemanticScholarCard` 傳入 `existingKeywords` + `onDeleteExistingKeyword`，展開 card 時可見並管理現有 keyword

---

## Phase 7: OpenAlex 實作（US4）

**Purpose**: 以 OpenAlex 作為主要免費學術論文 API（Semantic Scholar 因 API key 限制無法可靠使用）

**Independent Test**: 啟用 OpenAlex + 加入 keyword，執行 `make scrape SOURCE=openalex LIMIT=3`，確認資料庫出現 `source = 'openalex'` 的論文

### 後端實作（已完成）

- [x] T033 [P] 新增 `OpenAlexConfig` 至 `shared/selector_config.py`（type, max_results, days_back）；更新 `SelectorConfig` union 與 `build_selector_config()`
- [x] T034 [P] 新增 `"openalex_keyword"` 至 `shared/enums/scraper_keyword.py`
- [x] T035 [P] 新增 `OpenAlexKeyword` VO 至 `src/modules/collection/domain/value_objects/scraper_keyword.py`；更新 union 與 `build_scraper_keyword()`
- [x] T036 [P] 建立 `src/infrastructure/collection/clients/openalex_client.py`（含 `_reconstruct_abstract()` inverted index 還原、polite pool User-Agent、`OpenAlexRateLimitedError`）
- [x] T037 建立 `src/infrastructure/collection/scrapers/openalex_scraper.py`（結構同 SS scraper）
- [x] T038 更新 `src/infrastructure/collection/scrapers/scraper_factory.py` 加入 `OpenAlexConfig` 分支
- [x] T039 [P] 更新所有 `__init__.py` export（clients、scrapers、value_objects）
- [x] T040 [P] 新增 `api.openalex.org: 5.0 RPM` 至 `src/infrastructure/shared/http/rate_limiter.py`
- [x] T041 [P] 更新 `src/infrastructure/persistence/collection/scraper_setting_repo_impl.py` `isinstance` check 加入 `OpenAlexConfig`
- [x] T042 [P] 更新 `backend/schemas/scraper_setting.py` Literal 加入 `"openalex"`

### 前端實作（已完成）

- [x] T043 [P] 新增 OpenAlex i18n key 至 `en.json` 與 `zh-TW.json`
- [x] T044 [P] 建立 `frontend/components/features/scraper/openalex-keyword-manager.tsx`
- [x] T045 更新 `frontend/app/admin/scraper-settings/page.tsx`：新增 `OpenAlexSettingCard`、`AddOpenAlexCard`、state、handler、AccordionSection
- [x] T046 [P] 更新 `frontend/lib/api/scraper-settings.ts` source_type union 加入 `openalex`

### 測試（已完成）

- [x] T047 [P] 撰寫 `src/tests/unit/infrastructure/collection/clients/test_openalex_client.py`（abstract 還原、URL 優先順序、429 處理、parse failure）
- [x] T048 [P] 撰寫 `src/tests/unit/infrastructure/collection/scrapers/test_openalex_scraper.py`（discover、no keywords、rate limited、fetch with/without PDF）
- [x] T049 [P] 撰寫 `frontend/tests/unit/openalex-keyword-manager.test.tsx`

**Checkpoint**: OpenAlex 完整可測試

---

---

## Phase 9: Bug Fixes（2026-06-05 補充）

**Background**: 整合測試與實際執行中發現的問題修正

- [x] T050 [P] 修正 `src/infrastructure/collection/scrapers/scraper_factory.py`：SS + OA client 加入 `with_skip_retry_status(frozenset({429}))`，避免 429 觸發 8 分鐘 tenacity retry（同 ArXiv 模式）
- [x] T051 [P] 修正 `src/infrastructure/collection/collection_pipeline.py`：為 `semantic_scholar`、`openalex` source_type 硬編碼正確 API host（`api.semanticscholar.org` / `api.openalex.org`），修正原本兩者共用同一 per-host queue 的問題
- [x] T052 [P] 修正 `src/infrastructure/shared/http/user_agent.py`：從 `Accept-Encoding` 移除 `br`（Brotli），修正 OpenAlex 回傳 Brotli 壓縮內容但 `requests` 無法解碼導致的 JSONDecodeError
- [x] T053 [P] 更新 `src/infrastructure/collection/clients/openalex_client.py`：新增 `_BASE_FILTERS`（type:article, has_abstract:true, is_retracted:false）並將排序改為 `relevance_score:desc`，提升結果品質

---

## Phase 10: Article Source Attribution（US5 — FR-018~FR-021）

**Goal**: 文章卡片顯示真實原始出處（arxiv/期刊名）而非聚合器名稱；後端暴露 `via_source` / `original_source` 欄位

- [x] T054 [P] 更新 `src/infrastructure/collection/clients/openalex_client.py`：新增 `OpenAlexEntry.original_source`；`_parse_entry()` 從 arxiv_id 或 `primary_location.source.display_name` 解析
- [x] T055 [P] 更新 `src/infrastructure/collection/clients/semantic_scholar_client.py`：新增 `SemanticScholarEntry.original_source`；arxiv_id 存在 → "arxiv"，否則 → "semanticscholar"
- [x] T056 [P] 更新 `src/infrastructure/collection/scrapers/openalex_scraper.py` + `semantic_scholar_scraper.py`：`discover()` metadata 與 `fetch()` extra 均加入 `via_source` 與 `original_source`
- [x] T057 [P] 更新 `backend/routers/articles.py`：`ArticleOut` + `ArticleDetailOut` 新增 `via_source: Optional[str]` + `original_source: Optional[str]`；`_article_out()` 從 `metadata_` 讀取；`get_article` 同步
- [x] T058 [P] 新增 `frontend/components/features/articles/source-utils.ts`：`deriveDisplaySource(url, source, originalSource?)` + `formatViaSource(viaSource)` 共用工具
- [x] T059 [P] 更新 `frontend/lib/api/articles.ts`：`Article` 新增 `via_source?` + `original_source?`；更新 `ArticleDetail`
- [x] T060 [P] 更新 `frontend/components/features/articles/article-card.tsx`：使用 `deriveDisplaySource` 顯示原始出處，`via_source` 存在時顯示 "via OpenAlex" / "via Semantic Scholar" 小標籤
- [x] T061 [P] 更新 `frontend/components/features/articles/article-detail-dialog.tsx`：同 T060，加入 `url` + `via_source` + `original_source` prop
- [x] T062 [P] 更新 `frontend/components/features/monitoring/traces-table.tsx`：`ArticleDetailDialog` 補入 `url` + `via_source` + `original_source` prop

**Checkpoint**: US5 完整可測試 ✅

---

## Phase 11: Aggregator Filter（US6 — FR-022~FR-023）

**Goal**: 文章列表與 Knowledge Graph 新增 Aggregator 篩選維度

- [x] T063 更新 `backend/routers/articles.py`：`list_articles` 新增 `aggregator: List[str] = Query(default=[])` 參數；`get_articles_paginated` 支援 `aggregators` 過濾（`source IN aggregators`）
- [x] T064 [P] 更新 `frontend/lib/api/articles.ts`：`ArticleListParams` 新增 `aggregator?: string[]`；`fetchArticles` append aggregator params
- [x] T065 [P] 更新 `frontend/lib/api/graph.ts`：`GraphFilters` 新增 `aggregator?: string[]`
- [x] T066 更新 `frontend/hooks/use-pagination.ts`：新增 `aggregators` URL state；`setFilters` 支援 `aggregator` 更新；`activeFilterCount` 計入
- [x] T067 更新 `frontend/components/features/articles/filter-bar.tsx`：新增 `aggregators: string[]` prop；加入 Aggregator `MultiSelectPopover`（固定選項：openalex、semantic_scholar）；`onApply` / `handleClear` 同步
- [x] T068 更新 `frontend/app/home-page-content.tsx`：從 `usePagination` 取 `aggregators`，傳入 `FilterBar` 與 `fetchArticles`
- [x] T069 [P] 更新 `frontend/components/features/graph/knowledge-graph.tsx`：`FilterBar` 補入 `aggregators` prop + `activeFilterCount` 計算
- [x] T070 [P] 更新 i18n：`en.json` + `zh-TW.json` 新增 `filterBar.aggregator`（"Aggregator" / "聚合器"）
- [x] T071 [P] 更新 `frontend/components/features/scraper/scraper-source-card.tsx`：`ScraperSetting.source_type` union 加入 `"semantic_scholar" | "openalex"`（修正 TS 型別錯誤）
- [x] T072 [P] 修正前端測試型別問題：`filter-bar.test.tsx`（aggregators prop）、`error-boundary.test.tsx`（vi import + React import）、`article-share-page.test.tsx`（mockGetSearchParam 型別）

**Checkpoint**: US6 完整可測試 ✅

---

## Phase 8: Polish & Cross-Cutting Concerns（原 Phase 6）

- [ ] T023 在 Docker 環境執行 `make test` 確認所有既有及新增 scraper unit tests 通過（含 T047/T048）
- [ ] T024 [P] 在前端執行 `cd frontend && npm run test` 確認所有前端 unit tests 通過（含 T014/T049）
- [ ] T025 [P] 手動驗證流程：啟用 OpenAlex 來源 → 加入 keyword → `make scrape SOURCE=openalex LIMIT=3`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（Setup）**: 立即開始，無依賴
- **Phase 2（Foundational）**: 依賴 Phase 1 完成；T002/T003/T004 互相獨立可並行
- **Phase 3（US1）**: 依賴 Phase 2 完成；後端 T005→T006→T007 循序；前端 T008/T009 可並行，T010/T011 循序；測試 T012/T013/T014 可並行
- **Phase 4（US2）**: 依賴 Phase 3 完成；T015→T016 循序；T017/T018 可並行
- **Phase 5（US3）**: 依賴 Phase 2 完成；與 US2 可並行
- **Phase 6（SS Bug Fixes）**: 依賴 Phase 3 完成
- **Phase 7（OpenAlex）**: 依賴 Phase 2 完成；與 Phase 4/5 可並行
- **Phase 9（Bug Fixes）**: 依賴 Phase 7 完成；T050~T053 互相獨立
- **Phase 10（Article Source Attribution）**: 依賴 Phase 9 完成（需要 via_source 正確寫入）；T054~T062 大部分可並行
- **Phase 11（Aggregator Filter）**: 依賴 Phase 10 完成（前端 Article type 需有 via_source）；T063→T066→T067/T068 有順序；T064/T065/T069/T070/T071/T072 可並行
- **Phase 8（Polish）**: 依賴所有 Feature phase（3~11）完成

---

## Notes

- [P] tasks = 不同檔案、無依賴，可並行執行
- [Story] label 追蹤 task 對應的 user story
- PDF 下載（US2）需要外部網路；unit tests mock `PdfParser`
- ArXiv `arxiv_keyword` 的 DB 資料保留不刪除（系統層忽略），無需 migration
- 無需 Alembic migration（所有新設定存於既有 JSONB/varchar 欄位）
- **Semantic Scholar API key**：免費層需機構帳號申請，個人無法取得；首次執行即 HTTP 429（IP 層級限制）。SS 實作保留備用，主要使用 OpenAlex。
- **OpenAlex abstract**：以 inverted index（word → position list）格式儲存，`_reconstruct_abstract()` 還原為純文字後存入 `content` 欄位
- **OpenAlex polite pool**：設定環境變數 `OPENALEX_MAILTO=your@email.com` 以進入 10 req/sec 的 polite pool；未設定仍可運作但受預設限速
