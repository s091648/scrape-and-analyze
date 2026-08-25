import { getSession } from 'next-auth/react'

// ── Prometheus / Mimir response types ──────────────────────────────────────

export interface PrometheusMatrixResult {
  metric: Record<string, string>
  values: [number, string][] // [unix_timestamp, value_string]
}

export interface PrometheusResponse {
  status: 'success' | 'error'
  data?: {
    resultType: 'matrix' | 'vector' | 'scalar' | 'string'
    result: PrometheusMatrixResult[]
  }
  errorType?: string
  error?: string
}

// ── Loki response types ─────────────────────────────────────────────────────

export interface LokiStreamResult {
  stream: Record<string, string>
  values: [string, string][] // [nanosecond_timestamp_string, log_line]
}

export interface LokiResponse {
  status: 'success' | 'error'
  data?: {
    resultType: 'streams' | 'vector' | 'matrix'
    result: LokiStreamResult[]
    stats?: Record<string, unknown>
  }
}

// ── Tempo response types ────────────────────────────────────────────────────

export interface TempoSpanSetAttribute {
  key: string
  value: { stringValue?: string; intValue?: string; boolValue?: boolean }
}

export interface TempoSearchSpan {
  spanID: string
  startTimeUnixNano: string
  durationNanos: string
  attributes?: TempoSpanSetAttribute[]
}

export interface TempoSpanSet {
  spans: TempoSearchSpan[]
  matched: number
  attributes?: TempoSpanSetAttribute[]
}

export interface TempoTrace {
  traceID: string
  rootServiceName: string
  rootTraceName: string
  startTimeUnixNano: string
  durationMs?: number
  spanSet?: TempoSpanSet
  spanSets?: TempoSpanSet[]
  serviceStats?: Record<string, { spanCount: number }>
}

export interface TempoResponse {
  traces: TempoTrace[]
  metrics?: Record<string, unknown>
}

// ── OTLP trace response types (from GET /grafana/traces/{id}) ───────────────

export interface OtlpAttributeValue {
  stringValue?: string
  intValue?: string      // Tempo serialises int64 as a decimal string
  boolValue?: boolean
  doubleValue?: number
}

export interface OtlpAttribute {
  key: string
  value: OtlpAttributeValue
}

// span.add_event(name, attributes) on the Python SDK side (e.g. chatbot-plugin's
// "first_content"/"first_chunk" markers) — Tempo passes these through in the same
// OTLP/JSON shape as span-level attributes, just nested per event with its own timestamp.
export interface OtlpSpanEvent {
  timeUnixNano: string
  name: string
  attributes?: OtlpAttribute[]
}

export interface OtlpSpan {
  traceId: string
  spanId: string
  parentSpanId?: string
  name: string
  startTimeUnixNano: string
  endTimeUnixNano: string
  attributes: OtlpAttribute[]
  events?: OtlpSpanEvent[]
  status?: { code: number | string; message?: string }
}

export interface OtlpResourceSpans {
  resource: { attributes: OtlpAttribute[] }
  scopeSpans: Array<{ spans: OtlpSpan[] }>
}

export interface OtlpTraceResponse {
  batches: OtlpResourceSpans[]
}

// ── Query parameter types ───────────────────────────────────────────────────

export interface MetricsQueryParams {
  query: string
  start?: number // unix seconds
  end?: number   // unix seconds
  step?: string  // e.g. "60", "5m"
}

export interface MetricsBatchItem {
  query: string
  start?: number
  end?: number
  step?: string
}

// Loki's query_range endpoint (shared by both metric-shaped and raw log queries) expects
// start/end as nanosecond-epoch strings — see queryLogsBatch below. queryMetricsBatch above
// talks to Prometheus/Mimir instead, which uses unix-second numbers, so it keeps MetricsBatchItem.
export interface LokiMetricsBatchItem {
  query: string
  start?: string
  end?: string
  step?: string
}

export interface LogsQueryParams {
  query: string
  start?: string // nanosecond timestamp string
  end?: string   // nanosecond timestamp string
  limit?: number
  direction?: 'forward' | 'backward'
}

export interface TracesQueryParams {
  q?: string      // TraceQL expression
  start?: number  // unix seconds
  end?: number    // unix seconds
  limit?: number
  minDuration?: string // e.g. "100ms"
}

// ── Session token cache (avoids one getSession() call per query) ────────────
// Singleton promise prevents simultaneous callers from each firing getSession().

let _tokenCache: { token: string; expiry: number } | null = null
let _tokenPromise: Promise<Record<string, string>> | null = null

async function authHeaders(): Promise<Record<string, string>> {
  const now = Date.now()
  if (_tokenCache && _tokenCache.expiry > now) {
    return _tokenCache.token ? { Authorization: `Bearer ${_tokenCache.token}` } : {}
  }
  if (!_tokenPromise) {
    _tokenPromise = getSession().then(session => {
      const token = (session as { accessToken?: string } | null)?.accessToken ?? ''
      _tokenCache = { token, expiry: Date.now() + 60_000 }
      _tokenPromise = null
      return (token ? { Authorization: `Bearer ${token}` } : {}) as Record<string, string>
    }).catch(() => {
      _tokenPromise = null
      return {} as Record<string, string>
    })
  }
  return _tokenPromise
}

// ── Client functions ────────────────────────────────────────────────────────

function buildParams(obj: Record<string, string | number | undefined>): URLSearchParams {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined) p.set(k, String(v))
  }
  return p
}

export async function queryMetrics(params: MetricsQueryParams): Promise<PrometheusResponse> {
  const p = buildParams({
    query: params.query,
    start: params.start,
    end: params.end,
    step: params.step,
  })
  const res = await fetch(`/api/proxy/grafana/metrics?${p.toString()}`, {
    headers: await authHeaders(),
  })
  return res.json()
}

export async function queryMetricsBatch(items: MetricsBatchItem[]): Promise<PrometheusResponse[]> {
  const res = await fetch('/api/proxy/grafana/metrics/batch', {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  })
  const json = await res.json()
  return Array.isArray(json) ? json : [json]
}

export async function queryLokiMetricsBatch(items: LokiMetricsBatchItem[]): Promise<PrometheusResponse[]> {
  const res = await fetch('/api/proxy/grafana/loki-metrics/batch', {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  })
  const json = await res.json()
  return Array.isArray(json) ? json : [json]
}

export async function queryLogsBatch(items: LogsQueryParams[]): Promise<LokiResponse[]> {
  const res = await fetch('/api/proxy/grafana/logs/batch', {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  })
  const json = await res.json()
  return Array.isArray(json) ? json : [json]
}

export async function queryTracesBatch(items: TracesQueryParams[]): Promise<TempoResponse[]> {
  const res = await fetch('/api/proxy/grafana/traces/batch', {
    method: 'POST',
    headers: { ...(await authHeaders()), 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  })
  const json = await res.json()
  return Array.isArray(json) ? json : [json]
}

export async function queryLogs(params: LogsQueryParams): Promise<LokiResponse> {
  const p = buildParams({
    query: params.query,
    start: params.start,
    end: params.end,
    limit: params.limit,
    direction: params.direction,
  })
  const res = await fetch(`/api/proxy/grafana/logs?${p.toString()}`, {
    headers: await authHeaders(),
  })
  return res.json()
}

export async function queryTraces(params: TracesQueryParams = {}): Promise<TempoResponse> {
  const p = buildParams({
    q: params.q,
    start: params.start,
    end: params.end,
    limit: params.limit,
    minDuration: params.minDuration,
  })
  const res = await fetch(`/api/proxy/grafana/traces?${p.toString()}`, {
    headers: await authHeaders(),
  })
  return res.json()
}

export async function queryTraceById(traceId: string): Promise<OtlpTraceResponse> {
  const res = await fetch(`/api/proxy/grafana/traces/${traceId}`, {
    headers: await authHeaders(),
  })
  return res.json()
}