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

export interface TempoTrace {
  traceID: string
  rootServiceName: string
  rootTraceName: string
  startTimeUnixNano: string
  durationMs: number
  spanSets?: unknown[]
}

export interface TempoResponse {
  traces: TempoTrace[]
  metrics?: Record<string, unknown>
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
