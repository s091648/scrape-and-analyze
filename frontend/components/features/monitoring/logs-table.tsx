'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { queryLogs, queryTraceById, type LokiStreamResult, type LokiResponse, type OtlpSpan } from '@/lib/api/grafana'
import { TablePanel } from '@/components/ui/table-panel'
import { useI18n } from '@/lib/providers'
import { LokiLabel } from '@/lib/observability-constants'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { flattenSpans, buildSpanTree, findArticlePipelineSpans, findStageSpans, otlpIdToHex, type SpanNode } from '@/lib/otlp-utils'
import { LogDetailDialog, LEVEL_COLORS, type LogEntry } from './log-detail-dialog'
import { ArticleWorkflowDialog } from './article-workflow-dialog'

export type { LogEntry }

type LevelFilter = 'all' | 'error' | 'warning' | 'info'

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
  externalData?: LokiResponse
  onRefresh?: () => Promise<void>
  forcedLevel?: string
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
  // Priority order: url first (most useful), then source, error, counts, ids
  const priority = ['url', 'source', 'error', 'count', 'duration_seconds', 'published', 'new', 'duplicate', 'failed', 'remaining', 'skipped', 'run_id', 'article_id', 'analysis_id', 'model', 'input_tokens', 'output_tokens']
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
    if (/error/i.test(line)) return 'error'
    if (/warn/i.test(line)) return 'warning'
    return 'info'
  }
}

function parseMessage(line: string): string {
  try {
    const obj = JSON.parse(line)
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
      entries.push({
        _ms: ms,
        ts: new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        tsExact: new Date(ms).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        level: parseLevel(line),
        env,
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
}: LogsTableProps) {
  const { t } = useI18n()
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)
  const [filter, setFilter] = useState<LevelFilter>('all')
  const [selectedEntry, setSelectedEntry] = useState<LogEntry | null>(null)
  const [traceTarget, setTraceTarget] = useState<TraceTarget | null>(null)
  const [noSpanDialog, setNoSpanDialog] = useState(false)

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
    if (externalData === undefined) return
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
      if (pipelines.length === 0) { setNoSpanDialog(true); return }
      const pipeline = (spanId ? findPipelineForSpan(spans, spanId) : undefined) ?? pipelines[0]
      const stages = findStageSpans(tree, pipeline.spanId)
      setTraceTarget({ pipeline, stages, highlightSpanId: spanId })
    } catch { setNoSpanDialog(true) }
  }

  const activeLevel = forcedLevel ?? filter
  const visible = activeLevel === 'all' ? entries : entries.filter(e => e.level === activeLevel)

  const placeholder = notConfigured
    ? t('admin.grafanaNotConfigured')
    : error
    ? t('admin.failedToLoadLogs')
    : undefined

  const columns = [
    { key: 'ts',      label: t('admin.logColumnTime'),        className: 'w-32' },
    { key: 'level',   label: t('admin.logColumnLevel'),       className: 'w-16' },
    { key: 'env',     label: t('admin.logColumnEnvironment'), className: 'w-24' },
    { key: 'message', label: t('admin.logColumnMessage') },
  ]

  const toolbar = forcedLevel ? undefined : (
    <select
      className="text-xs border border-border rounded px-1 py-0.5 bg-background"
      value={filter}
      onChange={e => setFilter(e.target.value as LevelFilter)}
    >
      <option value="all">{t('admin.logFilterAll')}</option>
      <option value="error">{t('admin.logFilterError')}</option>
      <option value="warning">{t('admin.logFilterWarning')}</option>
      <option value="info">{t('admin.logFilterInfo')}</option>
    </select>
  )

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
        toolbar={toolbar}
      >
        {visible.length === 0 ? (
          <tr>
            <td colSpan={4} className="text-center py-8 text-muted-foreground text-xs">
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

      <Dialog open={noSpanDialog} onOpenChange={v => { if (!v) setNoSpanDialog(false) }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('admin.traceNoPipelineTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-muted-foreground">{t('admin.traceNoPipelineMessage')}</p>
        </DialogContent>
      </Dialog>
    </>
  )
}
