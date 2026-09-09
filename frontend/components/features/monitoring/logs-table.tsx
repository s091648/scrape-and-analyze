'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { queryLogs, queryTraceById, type LokiStreamResult, type LokiResponse, type OtlpSpan, type OtlpTraceResponse } from '@/lib/api/grafana'
import { TablePanel } from '@/components/ui/table-panel'
import { useI18n } from '@/lib/providers'
import { LokiLabel } from '@/lib/observability-constants'
import { ISO_ALPHA2_TO_NAME } from '@/lib/iso-country-codes'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { flattenSpans, buildSpanTree, findArticlePipelineSpans, findStageSpans, otlpIdToHex, type SpanNode } from '@/lib/otlp-utils'
import { LogDetailDialog, LEVEL_COLORS, HTTP_METHOD_COLORS, type LogEntry } from './log-detail-dialog'
import { ArticleWorkflowDialog } from './article-workflow-dialog'
import { RunWaterfallDialog } from './run-waterfall-dialog'

export type { LogEntry }

/** A click-to-filter selection on the log tables. Owned by LogsTab (so one click narrows all
 * three level tables), applied client-side against the already-fetched rows. */
export interface LogFilter {
  type: 'country' | 'session'
  value: string
}

interface LogsTableProps {
  title: string
  query: string
  from?: string
  to?: string
  limit?: number
  height?: number
  refreshInterval?: number
  className?: string
  tooltip?: string
  /** null means "controlled mode, data pending" — distinct from undefined ("self-fetch mode"),
   * so a parent batch-hook's initial not-yet-loaded state doesn't get misread as "please self-fetch". */
  externalData?: LokiResponse | null
  onRefresh?: () => Promise<void>
  forcedLevel?: string
  /** Adds Method + Path + Caller columns, populated from RequestLoggingMiddleware's "request"
   * event (only backend logs have them — the scraper never emits them). */
  showRequestColumns?: boolean
  /** user_id -> display name (username/name/email), for the Caller column — the bearer JWT
   * itself only ever carries the raw user_id (see backend/services/auth_service.py), so a
   * readable name has to be resolved client-side. Missing entries (guest/anonymous, or a
   * user_id not in the admin user list) just show the raw value. */
  callerNames?: Record<string, string>
  /** Active click-to-filter selection (see LogFilter). When set, only rows whose country /
   * session_id matches are shown. Client-side narrowing of the already-fetched rows only — it
   * does NOT re-query Loki, so a match older than the fetched window won't appear. Backend
   * ("request" event) rows only carry these fields, so this is inert without showRequestColumns. */
  logFilter?: LogFilter | null
  onLogFilterChange?: (filter: LogFilter | null) => void
}

function parseNsTime(t: string): string {
  const nowMs = Date.now()
  const nowNs = nowMs.toString() + '000000'
  if (/^now-/.test(t)) {
    const match = t.match(/^now-(\d+)([smhd])$/)
    if (!match) return nowNs
    const [, n, unit] = match
    const multipliers: Record<string, number> = { s: 1000, m: 60000, h: 3600000, d: 86400000 }
    const offsetMs = Number(n) * (multipliers[unit] ?? 1000)
    return (nowMs - offsetMs).toString() + '000000'
  }
  return t
}

function buildDetails(line: string): string | undefined {
  let obj: Record<string, unknown>
  try { obj = JSON.parse(line) } catch { return undefined }
  // Priority order: url first (most useful), then source, error, counts, ids. The
  // status_code/duration_ms/namespace/... entries are backend-only fields (request/
  // cache_lookup/cache_warmup_completed events) — see RequestLoggingMiddleware and
  // shared/cache/redis_gateway.py.
  const priority = [
    'url', 'query_params', 'payload', 'source', 'original_source', 'error', 'count',
    'duration_seconds', 'published', 'new', 'duplicate', 'failed', 'remaining', 'skipped',
    'run_id', 'article_id', 'analysis_id', 'model', 'input_tokens', 'output_tokens',
    'status_code', 'duration_ms', 'namespace', 'status', 'lang', 'reason', 'topics_warmed',
    'request_id',
  ]
  const parts: string[] = []
  for (const key of priority) {
    const val = obj[key]
    if (val === undefined || val === null || val === '') continue
    const str = String(val)
    const display = key === 'url' ? (str.length > 60 ? '…' + str.slice(-57) : str)
      : str.length > 40 ? str.slice(0, 37) + '…' : str
    parts.push(`${key}: ${display}`)
  }
  return parts.length ? parts.join(' · ') : undefined
}

function parseLevel(line: string): string {
  try {
    const obj = JSON.parse(line)
    return String(obj.level ?? obj.severity ?? 'info').toLowerCase()
  } catch {
    // Conventional "LEVEL: message" / "LEVEL - message" prefix used by plain-text logs.
    const prefixMatch = line.match(/^\s*(ERROR|WARN(?:ING)?|INFO)\b/i)
    if (prefixMatch) {
      const lvl = prefixMatch[1].toUpperCase()
      if (lvl === 'ERROR') return 'error'
      if (lvl.startsWith('WARN')) return 'warning'
      return 'info'
    }
    // httpx's own request tracing (`HTTP Request: GET ... "HTTP/1.1 200 OK"`) has no
    // level prefix at all — searching the whole line for "error"/"warn" anywhere
    // false-positives on request URLs that embed those words as query values (e.g.
    // this dashboard querying detected_level="warn" shows up as a WARNING line even
    // though the request itself succeeded). The HTTP status code is the only real
    // signal these lines carry, so derive the level from that instead.
    const statusMatch = line.match(/HTTP\/\d\.\d\s+(\d{3})/)
    if (statusMatch) {
      const status = Number(statusMatch[1])
      if (status >= 500) return 'error'
      if (status >= 400) return 'warning'
      return 'info'
    }
    return 'info'
  }
}

function parseMessage(line: string): string {
  try {
    const obj = JSON.parse(line)
    // The raw "request" event name says nothing on its own (every backend request logs the
    // same literal string) — Method/Path/Caller already have their own columns, but this
    // keeps the row self-describing even where those columns aren't shown (the detail dialog,
    // or this component reused without showRequestColumns).
    if (obj.event === 'request' && obj.method && obj.path) {
      const status = obj.status_code != null ? ` → ${obj.status_code}` : ''
      const duration = obj.duration_ms != null ? ` (${obj.duration_ms}ms)` : ''
      return `${obj.method} ${obj.path}${status}${duration}`
    }
    return String(obj.event ?? obj.message ?? obj.msg ?? line)
  } catch {
    return line
  }
}

function flattenStreams(streams: LokiStreamResult[]): LogEntry[] {
  type Raw = LogEntry & { _ms: number }
  const entries: Raw[] = []
  for (const stream of streams) {
    const env = stream.stream[LokiLabel.ENV]
    for (const [tsNs, line] of stream.values) {
      const ms = Math.floor(Number(tsNs) / 1_000_000)
      let method: string | undefined
      let path: string | undefined
      let caller: string | undefined
      let country: string | undefined
      let sessionId: string | undefined
      try {
        const obj = JSON.parse(line)
        if (typeof obj.method === 'string') method = obj.method
        if (typeof obj.path === 'string') path = obj.path
        // RequestLoggingMiddleware (backend/middleware/logging.py) logs user_email when the
        // caller is authenticated, otherwise just user_id ("anonymous" for guest/no token).
        if (typeof obj.user_email === 'string') caller = obj.user_email
        else if (typeof obj.user_id === 'string') caller = obj.user_id
        // geo_country (GeoIP alpha-2) and session_id (X-Session-Id header) — "request" events only.
        if (typeof obj.geo_country === 'string') country = obj.geo_country
        if (typeof obj.session_id === 'string') sessionId = obj.session_id
      } catch { /* not JSON — nothing to extract */ }
      entries.push({
        _ms: ms,
        ts: new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        tsExact: new Date(ms).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        level: parseLevel(line),
        env,
        method,
        path,
        caller,
        country,
        sessionId,
        message: parseMessage(line),
        details: buildDetails(line),
        raw: line,
      })
    }
  }
  entries.sort((a, b) => b._ms - a._ms)
  return entries.map(({ _ms, ...e }) => e)
}

/**
 * Walk up the parent chain (using hex-normalised IDs) to find the article.pipeline
 * ancestor of spanIdHex. Handles both base64 and hex OTLP span IDs.
 */
function findPipelineForSpan(spans: OtlpSpan[], spanIdHex: string): OtlpSpan | undefined {
  const spanMap = new Map(spans.map(s => [otlpIdToHex(s.spanId), s]))
  let current = spanMap.get(spanIdHex)
  while (current) {
    if (current.name === 'article.pipeline') return current
    if (!current.parentSpanId) break
    current = spanMap.get(otlpIdToHex(current.parentSpanId))
  }
  return undefined
}

interface TraceTarget {
  pipeline: OtlpSpan
  stages: SpanNode[]
  highlightSpanId?: string
}

export function LogsTable({
  title,
  query,
  from = 'now-6h',
  to = 'now',
  limit = 100,
  height = 300,
  refreshInterval = 60,
  className,
  tooltip,
  externalData,
  onRefresh,
  forcedLevel,
  showRequestColumns,
  callerNames,
  logFilter,
  onLogFilterChange,
}: LogsTableProps) {
  const { t } = useI18n()
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)
  const [selectedEntry, setSelectedEntry] = useState<LogEntry | null>(null)
  const [traceTarget, setTraceTarget] = useState<TraceTarget | null>(null)
  const [waterfallTarget, setWaterfallTarget] = useState<{ traceId: string; data: OtlpTraceResponse } | null>(null)
  const [traceLoadFailed, setTraceLoadFailed] = useState(false)

  const fetch = useCallback(async () => {
    if (externalData !== undefined || onRefresh !== undefined) return
    const start = parseNsTime(from)
    const end = parseNsTime(to === 'now' ? `now-0s` : to)
    try {
      const res = await queryLogs({ query, start, end, limit })
      if ('error' in res && (res as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        return
      }
      if (res.status !== 'success' || !res.data) { setError(true); return }
      setEntries(flattenStreams(res.data.result as LokiStreamResult[]))
      setError(false)
      setNotConfigured(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [query, from, to, limit, externalData])

  useEffect(() => {
    if (externalData == null) return
    if ('error' in externalData && (externalData as { error: string }).error === 'not_configured') {
      setNotConfigured(true)
      setLoading(false)
      return
    }
    if (externalData.status !== 'success' || !externalData.data) {
      setError(true)
      setLoading(false)
      return
    }
    setEntries(flattenStreams(externalData.data.result as LokiStreamResult[]))
    setError(false)
    setNotConfigured(false)
    setLoading(false)
  }, [externalData])

  useEffect(() => { fetch() }, [fetch])

  useEffect(() => {
    if (externalData !== undefined || !refreshInterval || notConfigured) return
    const id = setInterval(fetch, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [fetch, refreshInterval, notConfigured, externalData])

  async function handleOpenTrace(traceId: string, spanId?: string) {
    try {
      const data = await queryTraceById(traceId)
      const spans = flattenSpans(data)
      const tree = buildSpanTree(spans)
      const pipelines = findArticlePipelineSpans(spans)
      if (pipelines.length > 0) {
        const pipeline = (spanId ? findPipelineForSpan(spans, spanId) : undefined) ?? pipelines[0]
        const stages = findStageSpans(tree, pipeline.spanId)
        setTraceTarget({ pipeline, stages, highlightSpanId: spanId })
        return
      }
      // findArticlePipelineSpans only ever matches a scraper.run trace's article.pipeline
      // children — a backend HTTP request trace (or any other app) never has one. Fall back
      // to the same generic span waterfall TracesTable's own trace-ID link opens, instead of
      // treating "not a scraper article trace" as a failure.
      setWaterfallTarget({ traceId, data })
    } catch { setTraceLoadFailed(true) }
  }

  const levelFiltered = forcedLevel ? entries.filter(e => e.level === forcedLevel) : entries
  const visible = logFilter
    ? levelFiltered.filter(e =>
        logFilter.type === 'country' ? e.country === logFilter.value : e.sessionId === logFilter.value,
      )
    : levelFiltered

  function toggleLogFilter(type: LogFilter['type'], value: string) {
    if (!onLogFilterChange) return
    const isActive = logFilter?.type === type && logFilter.value === value
    onLogFilterChange(isActive ? null : { type, value })
  }

  const placeholder = notConfigured
    ? t('admin.grafanaNotConfigured')
    : error
    ? t('admin.failedToLoadLogs')
    : undefined

  const columns = [
    { key: 'ts',      label: t('admin.logColumnTime'),        className: 'w-32' },
    { key: 'level',   label: t('admin.logColumnLevel'),       className: 'w-16' },
    ...(showRequestColumns ? [
      { key: 'method',  label: t('admin.logColumnMethod'),  className: 'w-16' },
      { key: 'path',    label: t('admin.logColumnPath'),    className: 'w-48' },
      { key: 'caller',  label: t('admin.logColumnCaller'),  className: 'w-32' },
      { key: 'country', label: t('admin.logColumnCountry'), className: 'w-28' },
      { key: 'session', label: t('admin.logColumnSession'), className: 'w-24' },
    ] : []),
    { key: 'env',     label: t('admin.logColumnEnvironment'), className: 'w-24' },
    { key: 'message', label: t('admin.logColumnMessage') },
  ]

  return (
    <>
      <TablePanel
        title={title}
        tooltip={tooltip}
        onRefresh={onRefresh}
        columns={columns}
        height={height}
        className={className}
        loading={loading}
        placeholder={placeholder}
        placeholderError={error}
      >
        {visible.length === 0 ? (
          <tr>
            <td colSpan={columns.length} className="text-center py-8 text-muted-foreground text-xs">
              {t('admin.noLogs')}
            </td>
          </tr>
        ) : (
          visible.map((entry, i) => (
            <tr
              key={i}
              className="border-b border-border last:border-0 hover:bg-muted/30 cursor-pointer"
              onClick={() => setSelectedEntry(entry)}
            >
              <td className="px-2 py-1 whitespace-nowrap text-muted-foreground">{entry.ts}</td>
              <td className={cn('px-2 py-1 whitespace-nowrap font-medium', LEVEL_COLORS[entry.level] ?? 'text-foreground')}>
                {entry.level.toUpperCase()}
              </td>
              {showRequestColumns && (
                <>
                  <td className="px-2 py-1 whitespace-nowrap">
                    {entry.method ? (
                      <span className={cn('inline-block px-1.5 py-0.5 rounded text-[10px] font-bold', HTTP_METHOD_COLORS[entry.method] ?? 'bg-muted text-muted-foreground')}>
                        {entry.method}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-2 py-1 font-mono text-[11px] max-w-0 overflow-hidden">
                    <div className="truncate">{entry.path ?? '—'}</div>
                  </td>
                  <td className="px-2 py-1 text-[11px] max-w-0 overflow-hidden">
                    <div className="truncate">{entry.caller ? (callerNames?.[entry.caller] ?? entry.caller) : '—'}</div>
                  </td>
                  <td className="px-2 py-1 text-[11px]">
                    {entry.country ? (
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); toggleLogFilter('country', entry.country!) }}
                        className={cn(
                          'cursor-pointer hover:underline',
                          logFilter?.type === 'country' && logFilter.value === entry.country && 'font-semibold text-primary',
                        )}
                      >
                        {ISO_ALPHA2_TO_NAME[entry.country] ?? entry.country}
                      </button>
                    ) : '—'}
                  </td>
                  <td className="px-2 py-1 font-mono text-[11px] max-w-0 overflow-hidden">
                    {entry.sessionId ? (
                      <button
                        type="button"
                        title={entry.sessionId}
                        onClick={e => { e.stopPropagation(); toggleLogFilter('session', entry.sessionId!) }}
                        className={cn(
                          'block w-full truncate text-left cursor-pointer hover:underline',
                          logFilter?.type === 'session' && logFilter.value === entry.sessionId && 'font-semibold text-primary',
                        )}
                      >
                        {entry.sessionId.slice(0, 8)}…
                      </button>
                    ) : '—'}
                  </td>
                </>
              )}
              <td className="px-2 py-1 text-muted-foreground whitespace-nowrap">{entry.env ?? '—'}</td>
              <td className="px-2 py-1 font-mono max-w-0 overflow-hidden">
                <div className="truncate">{entry.message}</div>
                {entry.details && (
                  <div className="truncate text-muted-foreground text-[10px] mt-0.5 opacity-70">{entry.details}</div>
                )}
              </td>
            </tr>
          ))
        )}
      </TablePanel>

      <LogDetailDialog
        entry={selectedEntry}
        onClose={() => setSelectedEntry(null)}
        onOpenTrace={handleOpenTrace}
      />

      {traceTarget && (
        <ArticleWorkflowDialog
          open
          onClose={() => setTraceTarget(null)}
          pipelineSpan={traceTarget.pipeline}
          stageSpans={traceTarget.stages}
          highlightedSpanId={traceTarget.highlightSpanId}
        />
      )}

      {waterfallTarget && (
        <RunWaterfallDialog
          open
          onClose={() => setWaterfallTarget(null)}
          traceId={waterfallTarget.traceId}
          trace={waterfallTarget.data}
        />
      )}

      <Dialog open={traceLoadFailed} onOpenChange={v => { if (!v) setTraceLoadFailed(false) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('admin.traceLoadFailedTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">{t('admin.traceLoadFailedMessage')}</p>
        </DialogContent>
      </Dialog>
    </>
  )
}
