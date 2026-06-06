# Implementation Plan: Grafana Tracing & Custom Monitoring Charts

**Branch**: `fix/grafana_trace_and_ui` | **Date**: 2026-05-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/010-grafana-tracing-charts/spec.md`

## Summary

兩個並行改動，共同目標是讓可觀測性監控真正能用：

1. **OTel Tracing**：在 `CollectionPipeline` 的各 stage 加入子 span，並在 `bootstrap.py` 的 event handler 訂閱處用 span wrapper 包裝，讓每次 scrape run 的追蹤樹具備足夠粒度。

2. **監控 UI**：以 Recharts + Grafana Cloud datasource HTTP API 取代現有的 image renderer proxy 方案，建立可在 free tier 運作的互動式圖表監控頁面。

## Technical Context

**Language/Version**: Python 3.11（scraper）、TypeScript + React 19（frontend）

**Primary Dependencies**:
- Python: `opentelemetry-sdk`、`opentelemetry-exporter-otlp-proto-http`（已安裝）
- Frontend (新增): `recharts`（charting library）

**Storage**: PostgreSQL — 無 schema 變更

**Testing**: pytest（unit + integration）、Vitest + Playwright（frontend）

**Target Platform**: Docker（開發）、Railway（production）

**Constraints**:
- Grafana Cloud free tier：不可用 iframe、image renderer
- DDD 架構：infrastructure layer 可加 OTel，application layer 不得直接 import OTel SDK
- Constitution VI：新 HTTP endpoint 和 pipeline steps 必須有 span

## Constitution Check

| Principle | Status | Note |
|-----------|--------|------|
| I. DDD | ✅ Pass | OTel spans 加在 `src/infrastructure/` 和 `bootstrap.py`；application handlers 不直接依賴 OTel |
| II. Atomic Frontend | ✅ Pass | 新 chart components 在 `components/features/monitoring/`；需要 Storybook stories |
| III. Test Discipline | ✅ Pass | tasks.md 必須包含 test phase；unit tests for tracing wrapper、component tests for charts |
| IV. Docker-First | ✅ Pass | 無需 bare-metal；新 env vars 加入 docker-compose |
| V. CI Boundary | ✅ Pass | 無 migration、無 CD 異動 |
| VI. Observability First-Class | ✅ Pass | 本 feature 即是 observability 改進 |
| VII. Code Style | ✅ Pass | 無 TODO comments；i18n for UI strings；Storybook required |

## Project Structure

### Documentation (this feature)

```text
specs/010-grafana-tracing-charts/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── grafana-proxy-api.md
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code Changes

```text
src/
├── infrastructure/
│   ├── collection/
│   │   └── collection_pipeline.py      MODIFIED — stage spans added
│   └── shared/
│       └── observability/
│           ├── __init__.py             MODIFIED — exports get_tracer, shutdown_tracing
│           └── span_wrappers.py        NEW — with_span / with_span_deferred / with_article_pipeline_span
│
├── bootstrap.py                        MODIFIED — uses tracing wrappers on all event_bus.subscribe()
├── entrypoints/cli/
│   └── main.py                         NO CHANGE — root span + shutdown already correct
│
└── shared/enums/
    └── observability.py                MODIFIED — SpanName enum added (ARTICLE_PIPELINE, handler names, etc.)

backend/
└── routers/
    └── grafana.py                      MODIFIED — all endpoints implemented:
                                             GET  /grafana/metrics
                                             POST /grafana/metrics/batch
                                             GET  /grafana/logs
                                             POST /grafana/logs/batch
                                             POST /grafana/loki-metrics/batch  ← LogQL metric queries (Prom-compat)
                                             GET  /grafana/traces
                                             POST /grafana/traces/batch
                                             GET  /grafana/traces/{trace_id}  ← NEW (OTLP detail)

frontend/
├── app/api/
│   └── grafana-proxy/
│       └── [...path]/
│           └── route.ts                EXISTS — 410 Gone (traffic goes through backend)
├── components/features/monitoring/
│   ├── grafana-panel.tsx               EXISTS — kept (legacy, unused by monitoring-content)
│   ├── stat-card.tsx                   EXISTS — onRefresh + refresh icon added
│   ├── metrics-chart.tsx               EXISTS — externalData + onRefresh added
│   ├── logs-table.tsx                  EXISTS — externalData + onRefresh added
│   ├── traces-table.tsx                EXISTS — collapsible rows + env column + dialogs added
│   ├── run-waterfall-dialog.tsx        NEW — Gantt span waterfall dialog
│   ├── article-workflow-dialog.tsx     NEW — Langfuse-style per-article stage card dialog
│   ├── stage-card.tsx                  NEW — individual stage card component
│   ├── log-detail-dialog.tsx           NEW — log row drill-down dialog (raw fields + correlation ID)
│   ├── failed-task-list.tsx            NEW — failed task panel (reuse in monitoring)
│   └── [*.stories.tsx]                 MODIFIED — WithData / WithRefresh variants
├── lib/
│   ├── api/
│   │   └── grafana.ts                  NEW (was grafana-api.ts) — all query functions + types
│   │                                        queryMetrics / queryMetricsBatch
│   │                                        queryLokiMetricsBatch  ← NEW (LogQL → Prom-compat)
│   │                                        queryLogs / queryLogsBatch
│   │                                        queryTraces / queryTracesBatch
│   │                                        queryTraceById  ← NEW
│   ├── otlp-utils.ts                   NEW — OTLP span parsing (flattenSpans, buildSpanTree,
│   │                                        findArticlePipelineSpans, findStageSpans, etc.)
│   └── observability-constants.ts      NEW — TypeScript mirror of shared/enums/observability.py
│                                            (SpanName, MetricName, LokiLabel, TraceQLResource, helpers)
└── app/admin/monitoring/
    └── monitoring-content.tsx          MODIFIED — global filter panel (time range: 6h/24h/3d/7d,
                                             environment: all/local/production; log level per-panel);
                                             useOperationsBatch / useLogsBatch / useTracesBatch hooks;
                                             all panels use externalData + onRefresh props;
                                             all stat/chart panels use queryLokiMetricsBatch (LogQL)
```

## Implementation Tasks (High-Level)

詳細任務由 `/speckit-tasks` 生成，以下為高層次順序：

### Phase A: OTel Tracing Spans（Python）

**A1**: 在 `collection_pipeline.py` 加入 stage spans（4 個，已實作）
- `pipeline.discover`（wraps `executor.run_discover()`）→ attributes: `sources.count`, `articles.discovered`
- `pipeline.fetch`（wraps `executor.run_fetch_only()`）→ attributes: `articles.to_fetch`, `articles.fetched`
- `pipeline.dedup`（wraps dedup filter logic）→ attributes: `articles.before_dedup`, `articles.after_dedup`, `articles.skipped`
- `pipeline.publish_articles`（wraps event publication loop）→ attribute: `articles.published`

**A2**: 提取 `src/infrastructure/shared/observability/span_wrappers.py`，定義三種 wrapper：
- `with_span(name, fn, tracer)` — 簡單包裹，用於 failed-event 和 pipeline-completed handlers
- `with_span_deferred(name, fn, bus, tracer)` — 延遲 publish，讓下游 handler span 成為 sibling 而非深度巢狀子節點
- `with_article_pipeline_span(fn, bus, tracer, pipeline_name, scraped_name)` — 建立 per-article parent span（`article.pipeline`）帶 `article.url`、`article.source`、`article.topic_id`，再 delegate 給 `with_span_deferred`

在 `bootstrap.py` 套用至所有 `event_bus.subscribe()` 呼叫：
- `ArticleScrapedEvent` → `with_article_pipeline_span` → `"article.pipeline"` + `"article.scraped.handle"`
- `ArticleProcessedEvent` → `with_span_deferred` → `"article.processed.handle"`
- `AnalysisFailedEvent` → `with_span` → `"article.analysis_failed.handle"`
- `TagNormalizationFailedEvent` → `with_span` → `"article.tag_normalization_failed.handle"`
- `TranslationFailedEvent` → `with_span` → `"article.translation_failed.handle"`
- `AnalysisCompletedEvent` → `with_span_deferred` → `"article.tag_normalization.handle"`
- `TagNormalizationCompletedEvent` → `with_span_deferred` → `"article.analysis_completed.handle"`
- `PipelineCompletedEvent` × 2 → `with_span` → `"scraper.pipeline_completed.handle"` / `"scraper.pipeline_completed.notify"`

**A3**: 撰寫 unit tests
- `src/tests/unit/test_tracing_wrapper.py`：mock tracer，verify span names 和 exception recording
- `src/tests/unit/test_collection_pipeline_spans.py`：verify pipeline span names
- `src/tests/unit/test_pipeline_span_attributes.py`：verify span attributes

### Phase B: Grafana Datasource Proxy（Frontend）

~~**B1**: 建立 `frontend/app/api/grafana-proxy/[...path]/route.ts`~~ → **實際改為後端 router 方案**（見 T004）
- `frontend/app/api/grafana-proxy/[...path]/route.ts` 回傳 410 Gone
- 所有 Grafana 代理流量改由 `backend/routers/grafana.py` 處理（透過 Next.js 反向 proxy）
- auth 由 backend JWT guard（`require_admin`）負責，不需 `getServerSession`

**B2**: 建立 `frontend/lib/api/grafana.ts`（注意：實際路徑為 `lib/api/grafana.ts`，非原計畫的 `lib/grafana-api.ts`）
- `queryMetrics(params)` → `GET /api/proxy/grafana/metrics`
- `queryMetricsBatch(items)` → `POST /api/proxy/grafana/metrics/batch`
- `queryLokiMetricsBatch(items)` → `POST /api/proxy/grafana/loki-metrics/batch`（LogQL metric queries）
- `queryLogs(params)` → `GET /api/proxy/grafana/logs`
- `queryLogsBatch(items)` → `POST /api/proxy/grafana/logs/batch`
- `queryTraces(params)` → `GET /api/proxy/grafana/traces`
- `queryTracesBatch(items)` → `POST /api/proxy/grafana/traces/batch`
- `queryTraceById(traceId)` → `GET /api/proxy/grafana/traces/{id}`
- 包含 TypeScript 型別定義（Prometheus / Loki / Tempo 回應格式）

### Phase C: Monitoring UI Components（Frontend）

**C1**: 安裝 `recharts`
```bash
npm install recharts
```

**C2**: 建立 `stat-card.tsx`
- 顯示單一數值（帶 label、可選 trend indicator）
- Storybook story

**C3**: 建立 `metrics-chart.tsx`
- 接收 PromQL query + time range props
- 呼叫 `queryMetrics()`，用 Recharts `LineChart` / `BarChart` 渲染
- Loading / error / "not configured" 三種狀態
- Storybook story

**C4**: 建立 `logs-table.tsx`
- 接收 LogQL query + time range props
- 呼叫 `queryLogs()`，顯示 timestamp + level + message
- 支援 level filter（error/warning/info）
- Storybook story

**C5**: 建立 `traces-table.tsx`
- 接收 TraceQL query + time range props
- 呼叫 `queryTraces()`，顯示 traceID + duration + root span name
- 每列可連結至 Grafana Cloud Tempo 查看完整 trace
- Storybook story

### Phase D: Monitoring Content 重構

**D1**: 修改 `monitoring-content.tsx`
- 替換 `GrafanaPanel`（image renderer）使用為新 chart components
- 各 tab 的 PromQL/LogQL/TraceQL 查詢 inline 定義（不需外部 dashboard UID）
- 移除 `dashboardUid` 和 `panelId` props（不再需要）

**D2**: 修改 `grafana-panel.tsx`（或移除）
- 如果只剩 "not configured" fallback 邏輯，考慮移除此元件，由各新元件自行處理

### Phase E: 環境變數與 Docker 配置

**E1**: 更新 `docker-compose.yml`（frontend service env）：
```yaml
GRAFANA_PROMETHEUS_URL: ${GRAFANA_PROMETHEUS_URL:-}
GRAFANA_LOKI_URL: ${GRAFANA_LOKI_URL:-}
GRAFANA_TEMPO_URL: ${GRAFANA_TEMPO_URL:-}
```

**E2**: 更新 `.env.example` 加入新變數說明

### Phase F: Tests

**F1**: Python unit tests（`src/tests/unit/`）
- `test_collection_pipeline_spans.py`：verify span creation in pipeline stages
- `test_tracing_wrapper.py`：verify `_with_span` wrapper creates child spans

**F2**: Frontend unit tests（`frontend/tests/unit/`）
- `grafana-api.test.ts`：mock fetch，verify proxy endpoint calls
- `metrics-chart.test.tsx`：verify loading/error/data states

**F3**: Frontend E2E（`frontend/tests/integration/`）
- `monitoring.spec.ts`：verify monitoring page loads without crash when Grafana not configured

### Phase G: Batch Updates & Per-Panel Refresh（US4）

**G1**: 在 `backend/routers/grafana.py` 新增三個 batch 端點：
- `POST /grafana/logs/batch`：接受 `list[LogsBatchItem]`，平行打 Loki `/query_range`，回傳 `list[LokiResponse]`
- `POST /grafana/traces/batch`：接受 `list[TracesBatchItem]`，平行打 Tempo `/api/search`，回傳 `list[TempoResponse]`
- `POST /grafana/loki-metrics/batch`：接受 `list[LokiMetricsBatchItem]`（query/start/end/step），平行打 Loki `/query_range` with metric queries（`count_over_time`、`rate`、`unwrap` 等），回傳 Prometheus-compatible matrix response（`data.resultType = "matrix"`）。此端點是所有 Operations / Logs / Traces tab 的 stat 和 chart 資料來源

**G2**: 在 `frontend/lib/api/grafana.ts` 新增 `queryLogsBatch()` 和 `queryTracesBatch()`（注意：實際路徑為 `lib/api/grafana.ts`，非原計畫的 `lib/grafana-api.ts`）

**G3**: 在 `monitoring-content.tsx` 實作三個 tab-level hooks：
- `useOperationsBatch()` — 1 次 metrics/batch（12 items: 8 stats + 4 charts）
- `useLogsBatch()` — `Promise.all([metrics/batch(3), logs/batch(4)])`
- `useTracesBatch()` — `Promise.all([metrics/batch(4), traces/batch(1)])`
- 各 hook 每 60s 重打；`refreshOne(index)` 觸發單一 panel 個別查詢

**G4**: 四個 panel components 各加 `externalData?` + `onRefresh?` props：
- `externalData` 有值時跳過內部 fetch 和 setInterval
- `onRefresh` 有值時右上角顯示 `RotateCw` icon button，loading 時 spin

**G5**: `monitoring-content.tsx` 重新佈線：移除 `usePromStatsBatch` 和 `LokiStat`，改用三個 tab hooks，pass props 到各 panel

**G6**: 加入全域篩選面板（Global Filter Panel，原計畫外新增）：
- Time Range 選擇器（6h / 24h / 3d / 7d）
- Environment 選擇器（all / local / production），對應 Tempo `deployment.environment` 和 Loki `env` label
- Log Level 未加入全域篩選；各 Logs tab panel 使用固定 LogQL level filter（error / warning / info 各自一個 panel）
- 篩選條件改變觸發各 hook 重新 fetch

**G7**: TracesTable 鑽取 UI（原計畫外新增）：
- `GET /grafana/traces/{trace_id}` backend 端點（正規化 `resourceSpans` → `batches`）
- `queryTraceById()` frontend function（`frontend/lib/api/grafana.ts`）
- OTLP 解析工具 `frontend/lib/otlp-utils.ts`（flattenSpans、buildSpanTree、findArticlePipelineSpans、findStageSpans 等）
- `frontend/lib/observability-constants.ts`（TypeScript mirror of `shared/enums/observability.py`）
- TracesTable 展開行：per-article sub-rows，`ArticleSubRow` component
- `run-waterfall-dialog.tsx`：Gantt 瀑布圖，SpanBar timeline
- `article-workflow-dialog.tsx`：Langfuse 式 stage cards
- `stage-card.tsx`：單一 stage 顯示
- `log-detail-dialog.tsx`：log row 展開 dialog，顯示完整結構化 log 欄位（event、correlation_id、timestamp 等）

**G8**: Storybook stories 各加 `WithData` / `WithRefresh` variant

**G9**: 更新 unit tests 覆蓋新 batch functions 和 externalData/onRefresh props

## Complexity Tracking

無 constitution 違規，此表為空。

所有 OTel span 加入均在 infrastructure / composition root layer，符合 DDD 原則。新前端元件均在 `components/features/monitoring/` 並附 Storybook。

> **實際交付範圍**比原計畫多出：全域篩選面板（G6）、TracesTable drill-down UI（G7）、OTLP 工具庫（otlp-utils.ts）、observability-constants.ts（TS/Python 共用常數鏡像）。這些均在 `fix/grafana_trace_and_ui` 分支一起交付。
