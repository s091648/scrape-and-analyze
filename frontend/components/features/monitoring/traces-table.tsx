'use client'

import { useEffect, useState, useCallback } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { queryTraces, queryTraceById, type TempoTrace, type TempoResponse, type OtlpTraceResponse, type OtlpSpan } from '@/lib/api/grafana'
import { TablePanel } from '@/components/ui/table-panel'
import { useI18n } from '@/lib/providers'
import {
  flattenSpans, buildSpanTree, findArticlePipelineSpans,
  findStageSpans, spanDurationMs, isErrorSpan, formatDuration,
} from '@/lib/otlp-utils'
import { RunWaterfallDialog } from './run-waterfall-dialog'
import { ArticleWorkflowDialog } from './article-workflow-dialog'
import { cn } from '@/lib/utils'

// ── Environment extraction ─────────────────────────────────────────────────────

function extractEnvironment(trace: TempoTrace): string | undefined {
  const attr = trace.spanSets?.[0]?.attributes?.find(
    a => a.key === 'deployment.environment' || a.key === 'resource.deployment.environment'
  )
  return attr?.value?.stringValue
}

// ── Time formatting ────────────────────────────────────────────────────────────

function parseRelativeSeconds(t: string): number {
  if (/^\d+$/.test(t)) return Number(t)
  const now = Math.floor(Date.now() / 1000)
  const match = t.match(/^now-(\d+)([smhd])$/)
  if (!match) return now
  const [, n, unit] = match
  const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 }
  return now - Number(n) * (multipliers[unit] ?? 1)
}

function formatStart(nanoStr: string): string {
  const ms = Number(BigInt(nanoStr) / 1_000_000n)
  return new Date(ms).toLocaleString()
}

// ── Article sub-row ────────────────────────────────────────────────────────────

interface ArticleSubRowProps {
  pipelineSpan: OtlpSpan
  stageSpans: OtlpSpan[]
  onView: (ps: OtlpSpan, ss: OtlpSpan[]) => void
}

// Columns: expand | traceId | root | service | env | dur | start  (7 total)
function ArticleSubRow({ pipelineSpan, stageSpans, onView }: ArticleSubRowProps) {
  const url = pipelineSpan.attributes.find(a => a.key === 'article.url')?.value?.stringValue ?? '—'
  const durationMs = spanDurationMs(pipelineSpan)
  const error = isErrorSpan(pipelineSpan)
  const truncUrl = url.length > 60 ? `…${url.slice(-57)}` : url

  return (
    <tr className="bg-muted/10 border-b border-border/30 hover:bg-muted/20">
      <td /> {/* expand col — empty indent */}
      {/* cols 2-4 (traceId, root, service) — show URL */}
      <td colSpan={3} className={cn('px-2 py-1 font-mono text-xs truncate max-w-0', error && 'text-destructive')}>
        {truncUrl}
      </td>
      {/* col 5 (env) — status badge */}
      <td className="px-2 py-1 text-xs text-center">
        {error
          ? <span className="text-destructive">✗</span>
          : <span className="text-emerald-600">✓</span>
        }
      </td>
      {/* col 6 (dur) — duration */}
      <td className="px-2 py-1 text-xs text-right tabular-nums">
        {formatDuration(durationMs)}
      </td>
      {/* col 7 (start) — view button */}
      <td className="px-2 py-1 text-xs">
        <button
          onClick={() => onView(pipelineSpan, stageSpans)}
          className="text-primary hover:underline"
        >
          view →
        </button>
      </td>
    </tr>
  )
}

// ── Props ──────────────────────────────────────────────────────────────────────

interface TracesTableProps {
  title: string
  query?: string
  from?: string
  to?: string
  limit?: number
  height?: number
  refreshInterval?: number
  grafanaUrl?: string
  className?: string
  tooltip?: string
  externalData?: TempoResponse
  onRefresh?: () => Promise<void>
}

// ── Main component ─────────────────────────────────────────────────────────────

export function TracesTable({
  title,
  query,
  from = 'now-24h',
  to = 'now',
  limit = 20,
  height = 300,
  refreshInterval = 60,
  grafanaUrl: _grafanaUrl,
  className,
  tooltip,
  externalData,
  onRefresh,
}: TracesTableProps) {
  const { t } = useI18n()
  const [traces, setTraces] = useState<TempoTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)

  // expand/collapse state
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [traceDetails, setDetails] = useState<Map<string, OtlpTraceResponse>>(new Map())
  const [loadingTrace, setLoadingTrace] = useState<Set<string>>(new Set())

  // dialog state
  const [waterfallTarget, setWaterfallTarget] = useState<{ traceId: string; data: OtlpTraceResponse } | null>(null)
  const [workflowTarget, setWorkflowTarget] = useState<{ pipeline: OtlpSpan; stages: OtlpSpan[] } | null>(null)

  // ── Data fetch ───────────────────────────────────────────────────────────────

  const fetch = useCallback(async () => {
    if (externalData !== undefined || onRefresh !== undefined) return
    const start = parseRelativeSeconds(from === 'now' ? String(Math.floor(Date.now() / 1000)) : from)
    const end   = parseRelativeSeconds(to   === 'now' ? String(Math.floor(Date.now() / 1000)) : to)
    try {
      const res = await queryTraces({ q: query, start, end, limit })
      if ('error' in res && (res as { error: string }).error === 'not_configured') {
        setNotConfigured(true); return
      }
      setTraces(res.traces ?? [])
      setError(false); setNotConfigured(false)
    } catch { setError(true) }
    finally { setLoading(false) }
  }, [query, from, to, limit, externalData])

  useEffect(() => {
    if (externalData === undefined) return
    if ('error' in externalData && (externalData as { error: string }).error === 'not_configured') {
      setNotConfigured(true); setLoading(false); return
    }
    setTraces(externalData.traces ?? [])
    setError(false); setNotConfigured(false); setLoading(false)
  }, [externalData])

  useEffect(() => { fetch() }, [fetch])
  useEffect(() => {
    if (externalData !== undefined || !refreshInterval || notConfigured) return
    const id = setInterval(fetch, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [fetch, refreshInterval, notConfigured, externalData])

  // ── Expand handler ────────────────────────────────────────────────────────────

  const toggleExpand = useCallback(async (traceId: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(traceId)) { next.delete(traceId) } else { next.add(traceId) }
      return next
    })
    if (traceDetails.has(traceId)) return
    setLoadingTrace(prev => new Set([...prev, traceId]))
    try {
      const data = await queryTraceById(traceId)
      setDetails(prev => new Map([...prev, [traceId, data]]))
    } catch {
      // On fetch error, expanded row shows "No articles" fallback (detail map entry absent)
    } finally {
      setLoadingTrace(prev => { const s = new Set(prev); s.delete(traceId); return s })
    }
  }, [traceDetails])

  // ── Dialog openers ────────────────────────────────────────────────────────────

  function openWaterfall(trace: TempoTrace) {
    const data = traceDetails.get(trace.traceID)
    if (!data) {
      // If detail not loaded yet, load it then open
      queryTraceById(trace.traceID).then(d => {
        setDetails(prev => new Map([...prev, [trace.traceID, d]]))
        setWaterfallTarget({ traceId: trace.traceID, data: d })
      })
      return
    }
    setWaterfallTarget({ traceId: trace.traceID, data })
  }

  function openWorkflow(pipeline: OtlpSpan, stages: OtlpSpan[]) {
    setWorkflowTarget({ pipeline, stages })
  }

  // ── Derived state ─────────────────────────────────────────────────────────────

  const placeholder = notConfigured
    ? t('admin.grafanaNotConfigured')
    : error ? t('admin.failedToLoadTraces') : undefined

  const columns = [
    { key: 'expand',  label: '',                                      className: 'w-6' },
    { key: 'traceId', label: t('admin.traceColumnTraceId') },
    { key: 'root',    label: t('admin.traceColumnRootSpan') },
    { key: 'service', label: t('admin.traceColumnService') },
    { key: 'env',     label: t('admin.traceColumnEnvironment') },
    { key: 'dur',     label: t('admin.traceColumnDuration'),          align: 'right' as const },
    { key: 'start',   label: t('admin.traceColumnStart') },
  ]

  // ── Render ────────────────────────────────────────────────────────────────────

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
        {traces.length === 0 ? (
          <tr>
            <td colSpan={columns.length} className="text-center py-8 text-muted-foreground text-xs">
              {t('admin.noTraces')}
            </td>
          </tr>
        ) : (
          traces.map(trace => {
            const isExpanded = expanded.has(trace.traceID)
            const isLoading  = loadingTrace.has(trace.traceID)
            const detail     = traceDetails.get(trace.traceID)
            const environment = extractEnvironment(trace)

            // Build article rows from cached detail
            let articleRows: { pipeline: OtlpSpan; stages: OtlpSpan[] }[] = []
            if (detail) {
              const spans = flattenSpans(detail)
              const tree  = buildSpanTree(spans)
              articleRows = findArticlePipelineSpans(spans).map(ps => ({
                pipeline: ps,
                stages: findStageSpans(tree, ps.spanId),
              }))
            }

            return (
              <>
                {/* ── Main run row ── */}
                <tr
                  key={trace.traceID}
                  className="border-b border-border last:border-0 hover:bg-muted/30"
                >
                  <td className="px-1 py-1">
                    <button
                      onClick={() => toggleExpand(trace.traceID)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={isExpanded ? 'Collapse' : 'Expand'}
                    >
                      {isExpanded
                        ? <ChevronDown className="h-3.5 w-3.5" />
                        : <ChevronRight className="h-3.5 w-3.5" />
                      }
                    </button>
                  </td>
                  <td className="px-2 py-1 font-mono text-primary">
                    <button
                      className="hover:underline"
                      onClick={() => openWaterfall(trace)}
                    >
                      {trace.traceID.slice(0, 8)}…
                    </button>
                  </td>
                  <td className="px-2 py-1 truncate max-w-[200px]">{trace.rootTraceName}</td>
                  <td className="px-2 py-1 text-muted-foreground truncate">{trace.rootServiceName}</td>
                  <td className="px-2 py-1 text-muted-foreground">{environment ?? '—'}</td>
                  <td className="px-2 py-1 text-right tabular-nums">
                    {formatDuration(trace.durationMs)}
                  </td>
                  <td className="px-2 py-1 text-muted-foreground whitespace-nowrap">
                    {formatStart(trace.startTimeUnixNano)}
                  </td>
                </tr>

                {/* ── Expanded article sub-rows ── */}
                {isExpanded && (
                  <tr key={`${trace.traceID}-exp`}>
                    <td colSpan={columns.length} className="p-0">
                      {isLoading && !detail ? (
                        <div className="px-8 py-2 text-xs text-muted-foreground">
                          {t('admin.loadingTrace')}
                        </div>
                      ) : articleRows.length === 0 ? (
                        <div className="px-8 py-2 text-xs text-muted-foreground">
                          {t('admin.noArticlesInRun')}
                        </div>
                      ) : (
                        <table className="w-full text-xs">
                          <tbody>
                            {articleRows.map(({ pipeline, stages }) => (
                              <ArticleSubRow
                                key={pipeline.spanId}
                                pipelineSpan={pipeline}
                                stageSpans={stages}
                                onView={openWorkflow}
                              />
                            ))}
                          </tbody>
                        </table>
                      )}
                    </td>
                  </tr>
                )}
              </>
            )
          })
        )}
      </TablePanel>

      {/* ── Dialogs ── */}
      {waterfallTarget && (
        <RunWaterfallDialog
          open
          onClose={() => setWaterfallTarget(null)}
          traceId={waterfallTarget.traceId}
          trace={waterfallTarget.data}
          onSelectArticle={(ps, ss) => {
            setWaterfallTarget(null)
            openWorkflow(ps, ss)
          }}
        />
      )}
      {workflowTarget && (
        <ArticleWorkflowDialog
          open
          onClose={() => setWorkflowTarget(null)}
          pipelineSpan={workflowTarget.pipeline}
          stageSpans={workflowTarget.stages}
        />
      )}
    </>
  )
}