'use client'

import { useEffect, useState, useCallback, Fragment } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { queryTraces, queryTraceById, type TempoTrace, type TempoResponse, type OtlpTraceResponse, type OtlpSpan } from '@/lib/api/grafana'
import { TablePanel } from '@/components/ui/table-panel'
import { useI18n } from '@/lib/providers'
import {
  flattenSpans, buildSpanTree, findArticlePipelineSpans, findWeeklyReportTopicSpans,
  findStageSpans, spanDurationMs, isErrorSpan, formatDuration, getAttr,
  extractTraceSearchEnvironment,
  type SpanNode,
} from '@/lib/otlp-utils'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailDialog } from '@/components/features/articles/article-detail-dialog'
import { RunWaterfallDialog } from './run-waterfall-dialog'
import { ArticleWorkflowDialog } from './article-workflow-dialog'
import { WeeklyReportTopicDialog } from './weekly-report-topic-dialog'
import { HttpMethodBadge, splitMethodSpanName } from './log-detail-dialog'
import { SpanName } from '@/lib/observability-constants'
import { cn } from '@/lib/utils'

// ── Duration computation ──────────────────────────────────────────────────────────

function resolveDurationMs(trace: TempoTrace): number {
  if (trace.durationMs != null && !isNaN(trace.durationMs)) return trace.durationMs
  // Fallback: compute from spanSet's durationNanos
  const spanSet = trace.spanSet ?? trace.spanSets?.[0]
  const nanos = spanSet?.spans?.[0]?.durationNanos
  if (nanos) return Number(BigInt(nanos) / 1_000_000n)
  return 0
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

// ── Article preview wrapper (lazy-loads article by ID) ─────────────────────────

function ArticlePreviewWrapper({ articleId, onClose }: { articleId: string | null; onClose: () => void }) {
  const { locale } = useI18n()
  // Store result keyed by id so we can derive loading without synchronous setState in the effect.
  const [result, setResult] = useState<{ id: string; detail: ArticleDetail | null } | null>(null)

  useEffect(() => {
    if (!articleId) return
    fetchArticleById(articleId, locale)
      .then(data => setResult({ id: articleId, detail: data }))
      .catch(() => setResult({ id: articleId, detail: null }))
  }, [articleId, locale])

  const isCurrent = result?.id === articleId
  const detail = isCurrent ? result!.detail : null
  const loading = !!articleId && !isCurrent

  return (
    <ArticleDetailDialog
      open={!!articleId}
      onOpenChange={v => { if (!v) onClose() }}
      id={articleId ?? ''}
      title={detail?.title ?? ''}
      source={detail?.source ?? ''}
      url={detail?.url ?? ''}
      via_source={detail?.via_source}
      original_source={detail?.original_source}
      published_at={detail?.published_at ?? null}
      content={detail?.content ?? ''}
      detail={detail}
      loading={loading}
    />
  )
}

// ── Article sub-row ────────────────────────────────────────────────────────────

interface ArticleSubRowProps {
  pipelineSpan: OtlpSpan
  stageSpans: SpanNode[]
  onView: (ps: OtlpSpan, ss: SpanNode[]) => void
  onPreviewArticle: (id: string) => void
}

// Columns: expand | traceId | root | service | env | dur | start  (7 total)
function ArticleSubRow({ pipelineSpan, stageSpans, onView, onPreviewArticle }: ArticleSubRowProps) {
  const allAttrs = stageSpans.flatMap(n => n.span.attributes ?? [])
  const title     = allAttrs.find(a => a.key === 'article.title')?.value?.stringValue ?? null
  const articleId = allAttrs.find(a => a.key === 'article.id')?.value?.stringValue ?? null

  const url = pipelineSpan.attributes?.find(a => a.key === 'article.url')?.value?.stringValue ?? '—'
  const durationMs = spanDurationMs(pipelineSpan)
  const error = isErrorSpan(pipelineSpan)
  const truncUrl = url.length > 40 ? `…${url.slice(-37)}` : url

  return (
    <tr className="bg-muted/10 border-b border-border/30 hover:bg-muted/20">
      <td /> {/* expand col — empty indent */}
      {/* cols 2-3 — article title (clickable if articleId available) */}
      <td colSpan={2} className={cn('px-2 py-1 text-xs truncate max-w-0', error && 'text-destructive')}>
        {title && articleId ? (
          <button
            onClick={() => onPreviewArticle(articleId)}
            className="hover:underline text-left truncate max-w-full text-primary cursor-pointer"
          >
            {title}
          </button>
        ) : (
          <span className="text-muted-foreground">{title ?? '—'}</span>
        )}
      </td>
      {/* col 4 — URL */}
      <td className="px-2 py-1 font-mono text-xs text-muted-foreground truncate max-w-0">
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
          className="text-primary hover:underline cursor-pointer"
        >
          view →
        </button>
      </td>
    </tr>
  )
}

// ── Weekly report topic sub-row ────────────────────────────────────────────────

interface TopicSubRowProps {
  topicSpan: OtlpSpan
  stageSpans: SpanNode[]
  onView: (ts: OtlpSpan, ss: SpanNode[]) => void
}

// Columns: expand | traceId | root | service | env | dur | start  (7 total)
function TopicSubRow({ topicSpan, stageSpans, onView }: TopicSubRowProps) {
  const topicName     = getAttr(topicSpan, 'topic.name') as string | undefined
  const articleCount  = getAttr(topicSpan, 'weekly_report.article_count') as number | undefined
  const outcome       = getAttr(topicSpan, 'weekly_report.outcome') as string | undefined
  const durationMs    = spanDurationMs(topicSpan)
  // A topic span itself only turns ERROR if execute() raised; partial failures
  // (image/summarize/notify) are swallowed there, so also check stage children.
  const error         = isErrorSpan(topicSpan) || stageSpans.some(n => isErrorSpan(n.span))

  return (
    <tr className="bg-muted/10 border-b border-border/30 hover:bg-muted/20">
      <td /> {/* expand col — empty indent */}
      {/* cols 2-3 — topic name */}
      <td colSpan={2} className={cn('px-2 py-1 text-xs truncate max-w-0', error && 'text-destructive')}>
        {topicName ?? '—'}
      </td>
      {/* col 4 — outcome / article count */}
      <td className="px-2 py-1 font-mono text-xs text-muted-foreground truncate max-w-0">
        {outcome ?? '—'}{articleCount != null && ` · ${articleCount} articles`}
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
          onClick={() => onView(topicSpan, stageSpans)}
          className="text-primary hover:underline cursor-pointer"
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
  /** null means "controlled mode, data pending" — distinct from undefined ("self-fetch mode"),
   * so a parent batch-hook's initial not-yet-loaded state doesn't get misread as "please self-fetch". */
  externalData?: TempoResponse | null
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
  const [workflowTarget, setWorkflowTarget] = useState<{ pipeline: OtlpSpan; stages: SpanNode[] } | null>(null)
  const [topicWorkflowTarget, setTopicWorkflowTarget] = useState<{ topic: OtlpSpan; stages: SpanNode[] } | null>(null)
  const [previewArticleId, setPreviewArticleId] = useState<string | null>(null)

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
    if (externalData == null) return
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

  function openWorkflow(pipeline: OtlpSpan, stages: SpanNode[]) {
    setWorkflowTarget({ pipeline, stages })
  }

  function openTopicWorkflow(topic: OtlpSpan, stages: SpanNode[]) {
    setTopicWorkflowTarget({ topic, stages })
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
            const environment = extractTraceSearchEnvironment(trace)

            // Build article/topic rows from cached detail. A run's root span name
            // determines which shape applies — scraper.run has article.pipeline
            // children, weekly_report.run has weekly_report.topic children.
            let articleRows: { pipeline: OtlpSpan; stages: SpanNode[] }[] = []
            let topicRows: { topic: OtlpSpan; stages: SpanNode[] }[] = []
            if (detail) {
              const spans = flattenSpans(detail)
              const tree  = buildSpanTree(spans)
              articleRows = findArticlePipelineSpans(spans).map(ps => ({
                pipeline: ps,
                stages: findStageSpans(tree, ps.spanId),
              }))
              topicRows = findWeeklyReportTopicSpans(spans).map(ts => ({
                topic: ts,
                stages: findStageSpans(tree, ts.spanId),
              }))
            }
            const isWeeklyReportRun = trace.rootTraceName === SpanName.WEEKLY_REPORT_RUN
            const isScraperRun = trace.rootTraceName === SpanName.SCRAPER_RUN
            // Only scraper.run / weekly_report.run traces have article/topic sub-rows to
            // expand into — a plain backend HTTP request trace (e.g. "GET /tag-groups") has
            // neither, so it isn't expandable here (its full span tree is still one click
            // away via the trace-ID waterfall link).
            const isExpandable = isScraperRun || isWeeklyReportRun
            const methodSpan = splitMethodSpanName(trace.rootTraceName)

            return (
              <Fragment key={trace.traceID}>
                {/* ── Main run row ── */}
                <tr
                  className="border-b border-border last:border-0 hover:bg-muted/30"
                >
                  <td className="px-1 py-1">
                    {isExpandable && (
                      <button
                        onClick={() => toggleExpand(trace.traceID)}
                        className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                        aria-label={isExpanded ? 'Collapse' : 'Expand'}
                      >
                        {isExpanded
                          ? <ChevronDown className="h-3.5 w-3.5" />
                          : <ChevronRight className="h-3.5 w-3.5" />
                        }
                      </button>
                    )}
                  </td>
                  <td className="px-2 py-1 font-mono text-primary">
                    <button
                      className="hover:underline cursor-pointer"
                      onClick={() => openWaterfall(trace)}
                    >
                      {trace.traceID.slice(0, 8)}…
                    </button>
                  </td>
                  <td className="px-2 py-1 truncate max-w-[200px]">
                    {methodSpan ? (
                      <span className="inline-flex items-center gap-1.5">
                        <HttpMethodBadge method={methodSpan.method} />
                        <span className="font-mono text-[11px] truncate">{methodSpan.path}</span>
                      </span>
                    ) : trace.rootTraceName}
                  </td>
                  <td className="px-2 py-1 text-muted-foreground truncate">{trace.rootServiceName}</td>
                  <td className="px-2 py-1 text-muted-foreground">{environment ?? '—'}</td>
                  <td className="px-2 py-1 text-right tabular-nums">
                    {formatDuration(resolveDurationMs(trace))}
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
                      ) : isWeeklyReportRun ? (
                        topicRows.length === 0 ? (
                          <div className="px-8 py-2 text-xs text-muted-foreground">
                            {t('admin.noTopicsInRun')}
                          </div>
                        ) : (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-border/50 text-muted-foreground">
                                <th className="w-6" /> {/* expand indent */}
                                <th colSpan={2} className="px-2 py-1 text-left font-medium">{t('admin.topicColumnTitle')}</th>
                                <th className="px-2 py-1 text-left font-medium">{t('admin.topicColumnArticleCount')}</th>
                                <th className="px-2 py-1 text-center font-medium">{t('admin.articleColumnStatus')}</th>
                                <th className="px-2 py-1 text-right font-medium">{t('admin.articleColumnDuration')}</th>
                                <th className="px-2 py-1 text-left font-medium">{t('admin.articleColumnAction')}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {topicRows.map(({ topic, stages }) => (
                                <TopicSubRow
                                  key={topic.spanId}
                                  topicSpan={topic}
                                  stageSpans={stages}
                                  onView={openTopicWorkflow}
                                />
                              ))}
                            </tbody>
                          </table>
                        )
                      ) : articleRows.length === 0 ? (
                        <div className="px-8 py-2 text-xs text-muted-foreground">
                          {t('admin.noArticlesInRun')}
                        </div>
                      ) : (
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-border/50 text-muted-foreground">
                              <th className="w-6" /> {/* expand indent */}
                              <th colSpan={2} className="px-2 py-1 text-left font-medium">{t('admin.articleColumnTitle')}</th>
                              <th className="px-2 py-1 text-left font-medium">{t('admin.articleColumnUrl')}</th>
                              <th className="px-2 py-1 text-center font-medium">{t('admin.articleColumnStatus')}</th>
                              <th className="px-2 py-1 text-right font-medium">{t('admin.articleColumnDuration')}</th>
                              <th className="px-2 py-1 text-left font-medium">{t('admin.articleColumnAction')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {articleRows.map(({ pipeline, stages }) => (
                              <ArticleSubRow
                                key={pipeline.spanId}
                                pipelineSpan={pipeline}
                                stageSpans={stages}
                                onView={openWorkflow}
                                onPreviewArticle={setPreviewArticleId}
                              />
                            ))}
                          </tbody>
                        </table>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })
        )}
      </TablePanel>

      {/* ── Dialogs ── */}
      <ArticlePreviewWrapper
        articleId={previewArticleId}
        onClose={() => setPreviewArticleId(null)}
      />
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
          onSelectTopic={(ts, ss) => {
            setWaterfallTarget(null)
            openTopicWorkflow(ts, ss)
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
      {topicWorkflowTarget && (
        <WeeklyReportTopicDialog
          open
          onClose={() => setTopicWorkflowTarget(null)}
          topicSpan={topicWorkflowTarget.topic}
          stageSpans={topicWorkflowTarget.stages}
        />
      )}
    </>
  )
}