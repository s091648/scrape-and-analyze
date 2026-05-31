# Data Model: Grafana Tracing & Custom Monitoring Charts

無新的資料庫 schema 變更。本功能涉及兩類結構：OTel Span 樹狀結構（記憶體中），以及前端 API 的請求／回應結構。

---

## OTel Span 樹狀結構

```
scraper.run                          (main.py — 已存在)
│  Attributes: run.id, run.correlation_id
│
├── pipeline.discover_and_fetch      (collection_pipeline.py — 新增)
│   │  Attributes: sources.count, articles.discovered
│   │
│   └── [per-source discover spans, optional in future]
│
├── pipeline.dedup                   (collection_pipeline.py — 新增)
│   │  Attributes: articles.before_dedup, articles.after_dedup, articles.skipped
│
└── pipeline.publish_articles        (collection_pipeline.py — 新增)
    │  Attributes: articles.published
    │
    ├── article.scraped.handle       (bootstrap.py wrapper — 新增)
    │   Attributes: article.url (if available), outcome
    │
    ├── article.processed.handle     (bootstrap.py wrapper — 新增)
    │   Attributes: article.id (if available)
    │
    ├── article.analysis.handle      (bootstrap.py wrapper — 新增)
    │   Attributes: article.id, analysis.provider (future)
    │
    └── article.translate.handle     (bootstrap.py wrapper — 新增)
        Attributes: article.id, languages
```

**Span 命名慣例**: `{domain}.{operation}` 全小寫，用 `.` 分隔層次

---

## 前端 Grafana Proxy — 請求與回應結構

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
GET /api/grafana-proxy/traces
?q=<TraceQL>            (e.g. { span.name = "scraper.run" })
&start=<unix_timestamp>
&end=<unix_timestamp>
&limit=<number>         (default 20)
&minDuration=<duration> (optional, e.g. "100ms")
```

**Response** (透傳 Tempo format):
```json
{
  "traces": [
    {
      "traceID": "abc123",
      "rootServiceName": "scrape-analyzer",
      "rootTraceName": "scraper.run",
      "startTimeUnixNano": "1748600000000000000",
      "durationMs": 45000
    }
  ]
}
```

---

## 環境變數

| 變數名稱 | 用途 | 範例值 |
|---------|------|--------|
| `GRAFANA_SA_TOKEN` | 已存在，所有 Grafana API 認證 | `glsa_xxx` |
| `GRAFANA_URL` | 已存在，SSRF 白名單用 | `https://xxx.grafana.net` |
| `GRAFANA_PROMETHEUS_URL` | 新增，Mimir query API base | `https://prometheus-prod-xx.grafana.net/api/prom` |
| `GRAFANA_LOKI_URL` | 新增，Loki query API base | `https://logs-prod-xx.grafana.net` |
| `GRAFANA_TEMPO_URL` | 新增，Tempo search API base | `https://tempo-prod-xx.grafana.net` |
