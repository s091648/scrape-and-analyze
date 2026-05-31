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
│   │   └── collection_pipeline.py      MODIFY — add stage spans
│   └── shared/
│       └── observability/
│           └── __init__.py             MODIFY — export tracing_span_wrapper if extracted
│
├── bootstrap.py                        MODIFY — wrap event_bus.subscribe() with span wrappers
└── entrypoints/cli/
    └── main.py                         NO CHANGE — root span + shutdown already correct

backend/
└── routers/
    └── grafana.py                      EXISTS — GET/POST /grafana/metrics(/batch), /grafana/logs, /grafana/traces
                                             MODIFY (Phase G): add POST /grafana/logs/batch, /grafana/traces/batch

frontend/
├── app/api/
│   └── grafana-proxy/
│       └── [...path]/
│           └── route.ts                EXISTS — 410 Gone (already moved to backend)
├── components/features/monitoring/
│   ├── grafana-panel.tsx               EXISTS — kept as-is (unused by monitoring-content)
│   ├── metrics-chart.tsx               EXISTS — MODIFY (Phase G): add externalData + onRefresh + refresh icon
│   ├── stat-card.tsx                   EXISTS — MODIFY (Phase G): add onRefresh + refresh icon
│   ├── logs-table.tsx                  EXISTS — MODIFY (Phase G): add externalData + onRefresh + refresh icon
│   ├── traces-table.tsx                EXISTS — MODIFY (Phase G): add externalData + onRefresh + refresh icon
│   ├── metrics-chart.stories.tsx       EXISTS — MODIFY (Phase G): add WithData variant
│   ├── stat-card.stories.tsx           EXISTS — MODIFY (Phase G): add WithData variant
│   ├── logs-table.stories.tsx          EXISTS — MODIFY (Phase G): add WithData variant
│   └── traces-table.stories.tsx        EXISTS — MODIFY (Phase G): add WithData variant
├── lib/
│   └── grafana-api.ts                  EXISTS — MODIFY (Phase G): add queryLogsBatch, queryTracesBatch
└── app/admin/monitoring/
    └── monitoring-content.tsx          EXISTS — MODIFY (Phase G): replace usePromStatsBatch + LokiStat
                                             with useOperationsBatch / useLogsBatch / useTracesBatch
```

## Implementation Tasks (High-Level)

詳細任務由 `/speckit-tasks` 生成，以下為高層次順序：

### Phase A: OTel Tracing Spans（Python）

**A1**: 在 `collection_pipeline.py` 加入 stage spans
- `pipeline.discover_and_fetch`（wraps `executor.run_streaming()`）
- `pipeline.dedup`（wraps dedup filter logic）
- `pipeline.publish_articles`（wraps event publication loop）
- 各 span 加入相關 attributes（article count, source count）

**A2**: 在 `bootstrap.py` 的 event handler 訂閱加入 span wrapper closure
```python
def _with_span(span_name: str, fn):
    tracer = get_tracer()
    def _wrapper(event):
        with tracer.start_as_current_span(span_name):
            return fn(event)
    return _wrapper
```
套用至：
- `ArticleScrapedHandler.handle` → `"article.scraped.handle"`
- `ArticleProcessedHandler.handle` → `"article.processed.handle"`
- `TagNormalizationHandler.handle` → `"article.tag_normalization.handle"`
- `AnalysisCompletedHandler.handle` → `"article.analysis_completed.handle"`

**A3**: 撰寫 unit tests
- `src/tests/unit/test_tracing_spans.py`：mock tracer，verify span names 和 attributes

### Phase B: Grafana Datasource Proxy（Frontend）

**B1**: 建立 `frontend/app/api/grafana-proxy/[...path]/route.ts`
- 根據 path segment 路由至 metrics / logs / traces
- 每個 sub-route 只允許轉發至對應的 datasource URL（SSRF 保護）
- 需要 authenticated session（`getServerSession`）

**B2**: 建立 `frontend/lib/grafana-api.ts`
- `queryMetrics(params)` → `GET /api/grafana-proxy/metrics`
- `queryLogs(params)` → `GET /api/grafana-proxy/logs`
- `queryTraces(params)` → `GET /api/grafana-proxy/traces`
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

**G1**: 在 `backend/routers/grafana.py` 新增 `POST /grafana/logs/batch` 和 `POST /grafana/traces/batch`
- 各自平行打 Loki / Tempo，pattern 同現有 metrics/batch
- 回傳 `list[LokiResponse]` / `list[TempoResponse]`

**G2**: 在 `frontend/lib/grafana-api.ts` 新增 `queryLogsBatch()` 和 `queryTracesBatch()`

**G3**: 在 `monitoring-content.tsx` 實作三個 tab-level hooks：
- `useOperationsBatch()` — 1 次 metrics/batch（12 items: 8 stats + 4 charts）
- `useLogsBatch()` — `Promise.all([metrics/batch(3), logs/batch(4)])`
- `useTracesBatch()` — `Promise.all([metrics/batch(4), traces/batch(1)])`
- 各 hook 每 60s 重打；`refreshOne(index)` 觸發單一 panel 個別查詢

**G4**: 四個 panel components 各加 `externalData?` + `onRefresh?` props：
- `externalData` 有值時跳過內部 fetch 和 setInterval
- `onRefresh` 有值時右上角顯示 `RotateCw` icon button，loading 時 spin

**G5**: `monitoring-content.tsx` 重新佈線：移除 `usePromStatsBatch` 和 `LokiStat`，改用三個 tab hooks，pass props 到各 panel

**G6**: Storybook stories 各加 `WithData` variant（傳 mock externalData）

**G7**: 更新 unit tests 覆蓋新 batch functions 和 externalData/onRefresh props

## Complexity Tracking

無 constitution 違規，此表為空。

所有 OTel span 加入均在 infrastructure / composition root layer，符合 DDD 原則。新前端元件均在 `components/features/monitoring/` 並附 Storybook。
