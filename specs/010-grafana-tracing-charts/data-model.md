# Data Model: Grafana Tracing & Custom Monitoring Charts

無新的資料庫 schema 變更。本功能涉及兩類結構：OTel Span 樹狀結構（記憶體中），以及前端 API 的請求／回應結構。

---

## OTel Span 樹狀結構

```
scraper.run                                (main.py — 已存在)
│  Attributes: run.id, run.correlation_id
│  Resource Attributes: service.name="scrape-analyzer",
│                       deployment.environment="production"|"local"
│
├── pipeline.discover_and_fetch            (collection_pipeline.py)
│   Attributes: sources.count, articles.discovered
│
├── pipeline.dedup                         (collection_pipeline.py)
│   Attributes: articles.before_dedup, articles.after_dedup, articles.skipped
│
├── pipeline.publish_articles              (collection_pipeline.py)
│   Attributes: articles.published
│   │
│   └── article.pipeline                  (bootstrap.py — with_article_pipeline_span)
│       │  [one per article, created by ArticleScrapedEvent handler]
│       │  Attributes: article.url, article.source, article.topic_id
│       │
│       ├── article.scraped.handle        (with_span_deferred — deferred sibling)
│       │
│       ├── article.processed.handle      (with_span_deferred — deferred sibling)
│       │
│       ├── article.tag_normalization.handle  (with_span_deferred — deferred sibling)
│       │
│       └── article.analysis_completed.handle (with_span_deferred — deferred sibling)
│           [triggers translation; article.translate.handle fires as child]
│
├── article.analysis_failed.handle         (with_span — ERROR status on failure)
├── article.tag_normalization_failed.handle (with_span — ERROR status on failure)
├── article.translation_failed.handle      (with_span — ERROR status on failure)
│
├── scraper.pipeline_completed.handle      (with_span — OTel metrics push)
└── scraper.pipeline_completed.notify      (with_span — Telegram notification)
```

**Span 命名慣例**: `{domain}.{operation}` 全小寫，用 `.` 分隔層次

**Span Wrapper 型別**:
- `with_span(name, fn, tracer)` — 同步包裹，不需 event-bus deferral（用於 failed-event、pipeline-completed handlers）
- `with_span_deferred(name, fn, bus, tracer)` — 收集 fn 內的 `bus.publish()` 呼叫，在 span 關閉後才重播，讓下游 span 成為同層 sibling 而非深度巢狀子節點
- `with_article_pipeline_span(fn, bus, tracer, pipeline_name, scraped_name)` — 建立 `article.pipeline` parent span，再用 `with_span_deferred` 包裹 `article.scraped.handle`；僅用於 `ArticleScrapedEvent`

---

## 前端 Grafana Proxy — 請求與回應結構

> 前端透過 Next.js proxy（`/api/proxy/grafana/*`）→ backend（`/grafana/*`）。
> Client 使用 `frontend/lib/api/grafana.ts`（非原設計的 `frontend/lib/grafana-api.ts`）。

### Metrics Query（對應 Prometheus query_range）

**Request**:
```
GET /api/grafana-proxy/metrics
?query=<PromQL>
&start=<unix_timestamp>
&end=<unix_timestamp>
&step=<duration>    (e.g. "60", "5m")
```

**Response** (透傳 Prometheus format):
```json
{
  "status": "success",
  "data": {
    "resultType": "matrix",
    "result": [
      {
        "metric": { "__name__": "scraper_runs_total", "job": "scraper" },
        "values": [[1748600000, "42"], [1748600060, "43"]]
      }
    ]
  }
}
```

### Logs Query（對應 Loki query_range）

**Request**:
```
GET /api/grafana-proxy/logs
?query=<LogQL>          (e.g. {app="scraper"} |= "error")
&start=<nanoseconds>
&end=<nanoseconds>
&limit=<number>         (default 100)
&direction=backward
```

**Response** (透傳 Loki format):
```json
{
  "status": "success",
  "data": {
    "resultType": "streams",
    "result": [
      {
        "stream": { "app": "scraper", "level": "error" },
        "values": [["1748600000000000000", "{\"level\":\"error\",\"event\":\"analysis_failed\"}"]]
      }
    ]
  }
}
```

### Traces Search（對應 Tempo search）

**Request**:
```
GET /api/proxy/grafana/traces
?q=<TraceQL>            (e.g. { resource.service.name = "scrape-analyzer" })
&start=<unix_timestamp>
&end=<unix_timestamp>
&limit=<number>         (default 20)
&minDuration=<duration> (optional, e.g. "100ms")
```

**Response** (透傳 Tempo format，含 spanSet 供 environment 欄位提取):
```json
{
  "traces": [
    {
      "traceID": "abc123",
      "rootServiceName": "scrape-analyzer",
      "rootTraceName": "scraper.run",
      "startTimeUnixNano": "1748600000000000000",
      "durationMs": 45000,
      "spanSet": {
        "spans": [{ "spanID": "...", "attributes": [{ "key": "deployment.environment", "value": { "stringValue": "production" } }] }],
        "matched": 1
      }
    }
  ]
}
```

### Trace Detail（對應 Tempo /api/traces/{id}）

用於 TracesTable 展開行和 RunWaterfallDialog / ArticleWorkflowDialog。

**Request**:
```
GET /api/proxy/grafana/traces/{traceId}
```

**Response** (OTLP JSON，backend 將 `resourceSpans` 正規化為 `batches`):
```json
{
  "batches": [
    {
      "resource": { "attributes": [{ "key": "service.name", "value": { "stringValue": "scrape-analyzer" } }] },
      "scopeSpans": [
        {
          "spans": [
            {
              "traceId": "abc123",
              "spanId": "def456",
              "parentSpanId": "parent789",
              "name": "article.pipeline",
              "startTimeUnixNano": "1748600000000000000",
              "endTimeUnixNano": "1748600045000000000",
              "attributes": [
                { "key": "article.url", "value": { "stringValue": "https://..." } },
                { "key": "article.source", "value": { "stringValue": "rss" } }
              ],
              "status": { "code": 0 }
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 環境變數

認證模型：各 datasource 使用獨立的 Basic Auth（`{USER}:{GRAFANA_API_KEY}`），不共用 Service Account Token。

| 變數名稱 | 用途 | 範例值 |
|---------|------|--------|
| `GRAFANA_URL` | 已存在，Grafana Cloud 主機（SSRF 白名單） | `https://xxx.grafana.net` |
| `GRAFANA_API_KEY` | 已存在，所有 datasource Basic Auth 的 password 欄位 | `glc_xxx` |
| `GRAFANA_OTLP_USER` | 已存在，OTel ingest 認證 user | 數字 ID |
| `GRAFANA_OTLP_ENDPOINT` | 已存在，OTel ingest 端點 | `https://otlp-gateway-xxx.grafana.net/otlp` |
| `GRAFANA_PROMETHEUS_URL` | Mimir query API base URL | `https://prometheus-prod-xx.grafana.net/api/prom` |
| `GRAFANA_PROMETHEUS_USER` | Mimir Basic Auth user | 數字 ID |
| `GRAFANA_LOKI_URL` | Loki query API base URL | `https://logs-prod-xx.grafana.net` |
| `GRAFANA_LOKI_USER` | Loki Basic Auth user | 數字 ID |
| `GRAFANA_TEMPO_URL` | Tempo search/trace API base URL | `https://tempo-prod-xx.grafana.net` |
| `GRAFANA_TEMPO_USER` | Tempo Basic Auth user | 數字 ID |
