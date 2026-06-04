# Tasks: Grafana Tracing & Custom Monitoring Charts

**Input**: Design documents from `specs/010-grafana-tracing-charts/`

**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/grafana-proxy-api.md ✓, quickstart.md ✓

**Tests**: 每個 Phase 均包含 test tasks（constitution §III 要求）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可與同 Phase 其他 [P] 任務並行（不同檔案、無相依）
- **[Story]**: 對應哪個 User Story (US1/US2/US3)

---

## Phase 1: Setup（共用基礎設施）

**Purpose**: 安裝新依賴、設定環境變數，為兩條工作流（Python tracing + Frontend charts）做準備

- [x] T001 安裝 recharts：在 frontend Docker container 執行 `npm install recharts`，確認 `frontend/package.json` + `frontend/package-lock.json` 更新
- [x] T002 [P] 在 `docker-compose.yml` 的 `frontend` service 加入三個新環境變數：`GRAFANA_PROMETHEUS_URL`、`GRAFANA_LOKI_URL`、`GRAFANA_TEMPO_URL`（值預設空字串 `${VAR:-}`）
- [x] T003 [P] 在 `.env.example`（或根目錄 `.env` 文件）加入三個新變數的說明及 Grafana Cloud 格式範例

**Checkpoint**: recharts 安裝完成，env vars 已宣告 → Phase 1 完成

---

## Phase 2: Foundational Frontend Infrastructure（阻塞 US2 所有圖表任務）

**Purpose**: 建立 Grafana datasource proxy 路由和 typed client，是所有 chart component 的共同依賴

**⚠️ 注意**: 此 Phase 僅阻塞 US2。US1（Python tracing）可在 Phase 2 進行的同時並行開始。

- [x] T004 ~~建立 `frontend/app/api/grafana-proxy/`~~ → **改為** 建立 `backend/routers/grafana.py`：`GET /grafana/metrics`（Prometheus query_range）、`GET /grafana/logs`（Loki query_range）、`GET /grafana/traces`（Tempo search）；使用 Basic Auth（per-datasource user + GRAFANA_API_KEY）；全部 require_admin；`frontend/app/api/grafana-proxy/route.ts` 改為 410 Gone；`backend/main.py` 註冊新 router
- [x] T005 [P] 建立 `frontend/lib/grafana-api.ts`：包含 `queryMetrics()`、`queryLogs()`、`queryTraces()` 三個 typed function，以及對應的 TypeScript 型別定義；呼叫 `/api/proxy/grafana/{metrics,logs,traces}`（透過 Next.js proxy → backend）；使用 `getSession()` 取得 session token 並加入 Bearer Authorization header

**Checkpoint**: proxy 路由和 client 完成 → US2 chart component 任務可以開始

---

## Phase 3: US1 — Operator Sees Live Traces in Grafana Cloud Tempo (Priority: P1) 🎯 MVP

**Goal**: 每次 scraper run 在 Grafana Cloud Tempo 中產生可見的 `scraper.run` trace，包含 `pipeline.discover_and_fetch`、`pipeline.dedup`、`pipeline.publish_articles` 三個子 span

**Independent Test**: `make scrape SOURCE=rss LIMIT=1 RUN_IMMEDIATELY=1` → 至 Grafana Cloud Tempo 搜尋 `{ resource.service.name = "scrape-analyzer" }` → 2 分鐘內出現 trace with at least one child span

### Tests for US1

- [x] T006 [P] [US1] 建立 `src/tests/unit/test_tracing_wrapper.py`：使用 mock tracer 驗證 `_with_span` closure：(a) 建立正確 span name 的 child span；(b) span 在 handler 執行後關閉；(c) handler exception 被正確 re-raise 且 span status 設為 ERROR
- [x] T007 [P] [US1] 建立 `src/tests/unit/test_collection_pipeline_spans.py`：mock `get_tracer()` 的 tracer，呼叫 `CollectionPipeline.run()` 後驗證 `start_as_current_span` 被呼叫的 span names 包含 `"pipeline.discover_and_fetch"` 和 `"pipeline.publish_articles"`

### Implementation for US1

- [x] T008 [US1] 修改 `src/bootstrap.py`：在 `build_collection_pipeline()` 函式內定義 `_with_span(span_name, fn)` closure helper（使用 `from src.infrastructure.shared.observability import get_tracer`），並將所有 `event_bus.subscribe()` 呼叫改為 wrapped 版本（`ArticleScrapedHandler` → `"article.scraped.handle"`；`ArticleProcessedHandler` → `"article.processed.handle"`；`TagNormalizationHandler` → `"article.tag_normalization.handle"`；`AnalysisCompletedHandler` → `"article.analysis_completed.handle"`）
- [x] T009 [US1] 修改 `src/infrastructure/collection/collection_pipeline.py`：在 `run()` 方法頂部取得 tracer（`tracer = get_tracer()`），用 `tracer.start_as_current_span("pipeline.discover_and_fetch")` 包裹 `executor.run_streaming()` 呼叫，用 `tracer.start_as_current_span("pipeline.dedup")` 包裹 dedup filter 邏輯，用 `tracer.start_as_current_span("pipeline.publish_articles")` 包裹 event publication loop；為每個 span 加入合適的 attributes（articles.discovered、articles.after_dedup、articles.published）

**Checkpoint**: `make test` 通過 → US1 完成，Python tracing 已就緒等待 env vars 驗證

---

## Phase 4: US2 — Monitoring Dashboard Shows Live Charts (Priority: P1)

**Goal**: `/admin/monitoring` 頁面用 Recharts 顯示互動式圖表（metrics / logs / traces），在 Grafana Cloud free tier 正常運作，不依賴 iframe 或 image renderer

**Independent Test**: 設定好 Grafana Cloud env vars → 打開 `/admin/monitoring` → 10 秒內各 panel 顯示 Recharts 圖表（非破圖或 "Grafana not configured" placeholder）

### Tests for US2

- [x] T010 [P] [US2] 建立 `frontend/tests/unit/grafana-api.test.ts`（Vitest）：mock `fetch`，驗證 `queryMetrics()`、`queryLogs()`、`queryTraces()` 分別呼叫正確的 proxy endpoint 並正確傳遞 query parameters
- [x] T011 [P] [US2] 建立 `frontend/tests/unit/stat-card.test.tsx`（Vitest）：驗證 stat-card 在有值/無值/loading 三種狀態下渲染正確
- [x] T012 [P] [US2] 建立 `frontend/tests/unit/metrics-chart.test.tsx`（Vitest）：mock `queryMetrics`，驗證 loading state、error state（API 失敗時顯示 error UI 而非 crash）、data state（Recharts chart rendered）
- [x] T013 [P] [US2] 建立 `frontend/tests/integration/monitoring.spec.ts`（Playwright）：無 Grafana env vars 時，monitoring 頁面所有 panel 顯示 "not configured" placeholder 而非錯誤；auth fixture 使用現有 `frontend/tests/integration/fixtures/auth-state.json`

### Implementation for US2

- [x] T014 [P] [US2] 建立 `frontend/components/features/monitoring/stat-card.tsx` 和 `frontend/components/features/monitoring/stat-card.stories.tsx`：顯示單一數值 + label，含 loading skeleton；Storybook story 包含 default、loading、zero value 三個 variant
- [x] T015 [P] [US2] 建立 `frontend/components/features/monitoring/metrics-chart.tsx` 和 `frontend/components/features/monitoring/metrics-chart.stories.tsx`：接收 `query: string`、`from: string`、`to: string`、`title: string` props；呼叫 `queryMetrics()` 並用 Recharts `LineChart` 或 `BarChart` 渲染；含 loading / error / "not configured" 三種狀態；Storybook 含各狀態 story
- [x] T016 [P] [US2] 建立 `frontend/components/features/monitoring/logs-table.tsx` 和 `frontend/components/features/monitoring/logs-table.stories.tsx`：接收 `query: string`、`from: string`、`to: string` props；呼叫 `queryLogs()`，以 timestamp + level badge + message 格式渲染 log rows；含 loading / error / empty / "not configured" 狀態；Storybook 含各狀態 story
- [x] T017 [P] [US2] 建立 `frontend/components/features/monitoring/traces-table.tsx` 和 `frontend/components/features/monitoring/traces-table.stories.tsx`：接收 `query: string`、`from: string`、`to: string` props；呼叫 `queryTraces()`，以 traceID + root span + duration 渲染，每列含連結至 Grafana Cloud Tempo 的外部連結；含 loading / error / empty / "not configured" 狀態；Storybook 含各狀態 story
- [x] T018 [US2] 修改 `frontend/app/admin/monitoring/monitoring-content.tsx`：將所有 `<Panel dashboardUid=... panelId=...>` 替換為對應的 `<StatCard>`、`<MetricsChart>`、`<LogsTable>`、`<TracesTable>` 元件；Operations tab 用 StatCard + MetricsChart；Logs tab 用 LogsTable；Traces tab 用 TracesTable；各元件使用 PromQL / LogQL / TraceQL 查詢（對應原有的 panelId 語意）（依賴 T014-T017）
- [x] T019 [US2] 修改 `frontend/components/features/monitoring/grafana-panel.tsx`：移除 image renderer proxy URL 邏輯（`/render/d-solo/...`）；若元件已無其他用途則移除並清理 `monitoring-content.tsx` 的 import（依賴 T018）

**Checkpoint**: `cd frontend && npm run test` + `npm run test:e2e` 通過；手動驗證 monitoring 頁面可渲染 → US2 完成

---

## Phase 5: US3 — Operator Can Identify Pipeline Stage Bottlenecks (Priority: P2)

**Goal**: Grafana Cloud Tempo 中的每個 trace 包含 discover/fetch/process/analyze 各 stage 的 child span，並附帶足夠的 attributes 讓操作者判斷瓶頸

**Independent Test**: 執行一次 scraper run → Tempo trace 包含至少 3 個 child span，並在 trace view 中可清楚看出各 stage 的耗時比例

**Prerequisites**: Phase 3 (US1) 完成 — US3 是對 US1 spans 的延伸

### Tests for US3

- [x] T020 [P] [US3] 建立 `src/tests/unit/test_pipeline_span_attributes.py`：驗證 `pipeline.discover_and_fetch` span 含 `sources.count` attribute；`pipeline.dedup` span 含 `articles.before_dedup` 和 `articles.after_dedup`；`pipeline.publish_articles` span 含 `articles.published`；error scenario 下 span status 設為 ERROR 並 record_exception

### Implementation for US3

- [x] T021 [US3] 強化 `src/infrastructure/collection/collection_pipeline.py` span attributes：在 `pipeline.discover_and_fetch` span 加入 `sources.count`（due settings 數量）和 `articles.discovered`（results 長度）；在 `pipeline.dedup` span 加入 `articles.before_dedup`、`articles.after_dedup`、`articles.skipped`；在 `pipeline.publish_articles` span 加入 `articles.published`；為 try-except 中的 exception 呼叫 `span.record_exception(e)` 和 `span.set_status(ERROR)`
- [x] T022 [P] [US3] 強化 `src/bootstrap.py` 的 `_with_span` wrapper：catch exception 時在 span 上呼叫 `span.record_exception(e)` 和 `span.set_status(StatusCode.ERROR, str(e))`，再 re-raise；更新 `_with_span` signature 確保 exception 被正確標記（需 import `from opentelemetry import trace as _otel`）

**Checkpoint**: `make test` 通過 → US3 完成

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: i18n、文件、Edge cases

- [x] T023 [P] 檢查並補充 `frontend/i18n/en.json` 和 `frontend/i18n/zh-TW.json`：確認 monitoring 頁面新元件（stat-card、metrics-chart、logs-table、traces-table）的 "not configured"、loading、error 等狀態文字有對應的 i18n key
- [ ] T024 [P] 更新 `specs/010-grafana-tracing-charts/quickstart.md`：補充實際驗證到的 Grafana Cloud endpoint URL 格式和 OTLP 設定細節（如有任何與原文件不符的發現）
- [ ] T025 按照 `specs/010-grafana-tracing-charts/quickstart.md` 的 "Verifying OTel Tracing Works" 和 "Verifying Monitoring UI Works" 章節做完整手動驗證；記錄結果

---

## Phase 7: US4 — Batch Updates & Per-Panel Refresh

**Purpose**: 改為 tab-level batch query 減少 HTTP 請求數；各 panel 加 refresh icon 支援手動個別更新。

**Prerequisites**: Phase 4 (US2) 完成 — 所有 panel components 已存在。

**Design doc**: `docs/superpowers/specs/2026-06-01-monitoring-batch-refresh-design.md`

### Backend

- [x] T026 [US4] 在 `backend/routers/grafana.py` 新增 `POST /grafana/logs/batch`：接受 `list[LogsBatchItem]`（query/start/end/limit/direction），`asyncio.gather` 平行打 Loki `/query_range`，回傳 `list[LokiResponse]`；env vars 缺少時回傳 503
- [x] T027 [P] [US4] 在 `backend/routers/grafana.py` 新增 `POST /grafana/traces/batch`：接受 `list[TracesBatchItem]`（q/start/end/limit/minDuration），`asyncio.gather` 平行打 Tempo `/api/search`，回傳 `list[TempoResponse]`；env vars 缺少時回傳 503
- [x] T026b [US4] 新增 `GET /grafana/traces/{trace_id}`：Tempo `/api/traces/{id}` proxy，正規化 `resourceSpans` → `batches`，用於 TracesTable 展開行和 Waterfall/Workflow dialogs

### Frontend API Layer

- [x] T028 [P] [US4] 在 `frontend/lib/api/grafana.ts` 新增 `queryLogsBatch()`、`queryTracesBatch()`、`queryTraceById()`，重用現有型別；同時建立 `frontend/lib/otlp-utils.ts`（OTLP span 解析）和 `frontend/lib/observability-constants.ts`（TS mirror of Python enum）

### Panel Components（可全部並行）

- [x] T029 [P] [US4] 修改 `frontend/components/features/monitoring/stat-card.tsx`：新增 `onRefresh?: () => void` prop；有值時右上角顯示 `RotateCw` icon button（lucide-react），loading 期間 `animate-spin`
- [x] T030 [P] [US4] 修改 `frontend/components/features/monitoring/metrics-chart.tsx`：新增 `externalData?: PrometheusResponse` 和 `onRefresh?: () => Promise<void>` props；controlled mode guard
- [x] T031 [P] [US4] 修改 `frontend/components/features/monitoring/logs-table.tsx`：新增 `externalData?: LokiResponse` 和 `onRefresh?: () => Promise<void>` props；controlled mode guard
- [x] T032 [P] [US4] 修改 `frontend/components/features/monitoring/traces-table.tsx`：新增 `externalData?: TempoResponse` 和 `onRefresh?: () => Promise<void>` props；controlled mode guard；新增 collapsible per-article sub-rows（`queryTraceById` on expand）；`RunWaterfallDialog` + `ArticleWorkflowDialog` + `stage-card.tsx`

### Hooks & Wiring（依賴 T028–T032）

- [x] T033 [US4] 在 `frontend/app/admin/monitoring/monitoring-content.tsx` 實作 `useOperationsBatch(timeRangeSeconds)`：一次 `queryMetricsBatch` 12 items（8 stats + 4 charts）；60s interval；`refreshOne(index)` 呼叫 `queryMetrics`
- [x] T034 [US4] 實作 `useLogsBatch(timeRangeSeconds, environment)`：`Promise.all([queryMetricsBatch(3), queryLogsBatch(4)])`；environment 參數動態修改 Loki stream selector
- [x] T035 [US4] 實作 `useTracesBatch()`：操作與 metrics 並行（Traces tab 直接透過 TracesTable 內部 fetch + externalData pattern）
- [x] T036 [US4] 重構 `monitoring-content.tsx`：移除 `usePromStatsBatch` 和 `LokiStat`；加入全域篩選面板（time range / environment / log level）；Operations/Logs/Traces 各呼叫對應 hook，props 傳入各 panel

### Tests

- [ ] T037 [P] [US4] 更新 `frontend/tests/unit/grafana-api.test.ts`：新增 `queryLogsBatch`、`queryTracesBatch`、`queryTraceById` 的測試（mock fetch，verify POST body 和 endpoint path）
- [ ] T038 [P] [US4] 在現有 component unit tests 中新增 `externalData` 和 `onRefresh` 測試：verify controlled mode 不觸發 fetch；verify refresh icon 在 `onRefresh` 有值時出現

**Checkpoint**: `cd frontend && npm run test` 通過；手動驗證 Network tab 只有 1 個 batch request per tab load → Phase 7 完成

> **注意**: T037/T038（unit tests for batch functions + controlled mode）尚未補齊，為技術債。

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
├── Phase 2 (Frontend Infra) → blocks Phase 4 (US2)
├── Phase 3 (US1)  ─────────────────────────────────────── independent
│                                                              ↓
└── Phase 5 (US3)  ─── depends on Phase 3 (US1) complete
Phase 4 (US2) ──── depends on Phase 2 (Foundational Frontend) complete
Phase 6 (Polish) ── depends on Phase 3 + Phase 4 + Phase 5 complete
```

### User Story Dependencies

- **US1 (P1)**: 可在 Phase 1 完成後立即開始，與 Phase 2 並行
- **US2 (P1)**: Phase 2 完成後開始（T004、T005 必須先完成）
- **US3 (P2)**: Phase 3（US1）完成後開始（延伸 US1 的 span）
- **US1 與 US2 完全獨立**：Python backend vs. TypeScript frontend，可由不同人並行完成

### Within Each User Story

- Tests（T006/T007, T010-T013, T020）應先寫，確認 fail 後再實作
- US2 中 T014-T017 可完全並行（不同檔案）
- T018 依賴 T014-T017 全部完成
- T019 依賴 T018 完成

---

## Parallel Examples

### US1 — 可同時進行

```bash
# 同時進行 tests + bootstrap 修改
Task T006: src/tests/unit/test_tracing_wrapper.py
Task T007: src/tests/unit/test_collection_pipeline_spans.py
# 待 tests 完成後：
Task T008: src/bootstrap.py
Task T009: src/infrastructure/collection/collection_pipeline.py  ← T008 與 T009 可並行
```

### US2 — 可同時進行

```bash
# 四個 chart components 完全並行
Task T014: stat-card.tsx + stat-card.stories.tsx
Task T015: metrics-chart.tsx + metrics-chart.stories.tsx
Task T016: logs-table.tsx + logs-table.stories.tsx
Task T017: traces-table.tsx + traces-table.stories.tsx
# 全部完成後：
Task T018: monitoring-content.tsx  ← sequential
Task T019: grafana-panel.tsx cleanup  ← sequential after T018
```

---

## Implementation Strategy

### MVP First（US1 + US2，停在 P1 驗證）

1. Phase 1: Setup（T001-T003）
2. Phase 2 + Phase 3 並行開始（T004-T009）
3. Phase 4: US2（T010-T019）
4. **Stop & Validate**: 手動驗證 OTel tracing + monitoring dashboard
5. Deploy if ready

### Full Delivery

1. Setup → Foundation → US1 + US2（並行）→ US3 → Polish
2. 每個 User Story 完成後獨立驗證
3. US3 加深 tracing 粒度，不影響 US1/US2 的可用性

---

## Notes

- `[P]` = 不同檔案、無相依，可並行
- 所有 frontend 新元件必須有 Storybook story（constitution §II）
- Python tests 在 Docker 執行：`make test`
- Frontend tests：`docker compose exec frontend npm run test`
- 不需要 Alembic migration（無 DB schema 變更）
- `grafana-proxy/` 目錄已存在（空目錄），直接在其中建立 `[...path]/route.ts`
