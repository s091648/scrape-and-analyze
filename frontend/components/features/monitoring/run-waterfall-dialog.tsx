'use client'

import { useState, useMemo, useEffect } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
import { queryProfile, type OtlpTraceResponse, type OtlpSpan, type FlamebearerTimeline } from '@/lib/api/grafana'
import {
  flattenSpans, buildSpanTree, spanDurationMs, isErrorSpan,
  getAttr, getResourceAttr, findStageSpans, formatDuration, articleRowStatus,
  type SpanNode,
} from '@/lib/otlp-utils'
import { SpanName, SERVICE_NAME, SERVICE_NAME_BACKEND } from '@/lib/observability-constants'
import { StageCard } from './stage-card'
import { HttpMethodBadge, splitMethodSpanName, DbSystemBadge } from './log-detail-dialog'
import { FlameGraphDialog, timelineToOverlayBars, CpuUtilizationStrip } from './flame-graph-dialog'
import { cn } from '@/lib/utils'
import { Activity } from 'lucide-react'

// ── Waterfall row builder ─────────────────────────────────────────────────────

interface WaterfallRow { span: OtlpSpan; depth: number; hasChildren: boolean }

function buildAllRows(spans: OtlpSpan[], tree: Map<string, OtlpSpan[]>): WaterfallRow[] {
  const rows: WaterfallRow[] = []
  const root = spans.find(s => !s.parentSpanId || s.parentSpanId === '')
  if (!root) return rows

  function visit(spanId: string, depth: number) {
    const children = (tree.get(spanId) ?? []).slice().sort(
      (a, b) => Number(BigInt(a.startTimeUnixNano) - BigInt(b.startTimeUnixNano))
    )
    for (const child of children) {
      const childHasChildren = (tree.get(child.spanId)?.length ?? 0) > 0
      rows.push({ span: child, depth, hasChildren: childHasChildren })
      visit(child.spanId, depth + 1)
    }
  }

  const rootHasChildren = (tree.get(root.spanId)?.length ?? 0) > 0
  rows.push({ span: root, depth: 0, hasChildren: rootHasChildren })
  visit(root.spanId, 1)
  return rows
}

// ── Span timeline bar ─────────────────────────────────────────────────────────

function SpanBar({
  span, rootStart, rootDurationNs,
}: { span: OtlpSpan; rootStart: bigint; rootDurationNs: bigint }) {
  if (rootDurationNs === 0n) return <div className="h-3 bg-muted rounded w-full" />
  const start = BigInt(span.startTimeUnixNano)
  const end   = BigInt(span.endTimeUnixNano)
  const offsetPct = Math.max(0, Number((start - rootStart) * 10000n / rootDurationNs) / 100)
  const widthPct  = Math.max(0.3, Number((end - start) * 10000n / rootDurationNs) / 100)
  const error = isErrorSpan(span)

  return (
    <div className="relative h-3 bg-muted/40 rounded w-full min-w-[80px]">
      <div
        className={cn('absolute h-full rounded', error ? 'bg-destructive/70' : 'bg-primary/60')}
        style={{ left: `${offsetPct}%`, width: `${widthPct}%` }}
      />
    </div>
  )
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface RunWaterfallDialogProps {
  open: boolean
  onClose: () => void
  traceId: string
  trace: OtlpTraceResponse
  onSelectArticle?: (pipelineSpan: OtlpSpan, stageSpans: SpanNode[]) => void
  onSelectTopic?: (topicSpan: OtlpSpan, stageSpans: SpanNode[]) => void
}

// ── Component ─────────────────────────────────────────────────────────────────

export function RunWaterfallDialog({
  open, onClose, traceId, trace, onSelectArticle, onSelectTopic,
}: RunWaterfallDialogProps) {
  const { t } = useI18n()

  const spans = flattenSpans(trace)
  const tree  = buildSpanTree(spans)
  const allRows = useMemo(() => buildAllRows(spans, tree), [spans, tree])

  // Prototype: any non-pipeline/non-topic row can be clicked to inspect its own
  // span attributes via StageCard — reuses the same component ArticleWorkflowDialog
  // renders per-stage cards with, just standalone instead of chained. No percentile
  // thresholds fetched here yet (that's ArticleWorkflowDialog-only for now).
  const [selectedSpan, setSelectedSpan] = useState<OtlpSpan | null>(null)
  // Both backend/main.py and src/entrypoints/cli/main.py run their own
  // setup_profiling() (fix/profiler_imprv) — which one applies to a given trace is
  // resolved below via isProfiledTrace/profileService. `flameGraphSpanId` is undefined
  // for the top-level "View Profile" button (whole padded window) and set when a row's
  // own "view profile for this span" is clicked (StageCard's onViewProfile below) — see
  // flame-graph-dialog.tsx's FlameGraphDialogProps.spanId doc comment for what scoping
  // by span actually narrows.
  const [showFlameGraph, setShowFlameGraph] = useState(false)
  const [flameGraphSpanId, setFlameGraphSpanId] = useState<string | undefined>(undefined)
  // Fetched unconditionally whenever a backend trace is open (not gated behind opening
  // FlameGraphDialog) — powers the always-visible CPU-utilization strip in the waterfall
  // itself (see CpuUtilizationStrip usage below), so the "is this gap actually CPU-bound or
  // just idle" question a span waterfall alone can't answer is visible without an extra click.
  const [profileTimeline, setProfileTimeline] = useState<FlamebearerTimeline | null>(null)
  const [profileSampleRate, setProfileSampleRate] = useState(1)

  // Default: collapse spans at depth >= 1 (second level and deeper)
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const initial = new Set<string>()
    for (const row of allRows) {
      if (row.depth >= 1 && row.hasChildren) initial.add(row.span.spanId)
    }
    return initial
  })

  // Reset collapsed state when a different trace is shown
  // allRows is intentionally excluded: it's derived from trace and changes reference
  // every render, adding it would cause an infinite loop.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const initial = new Set<string>()
    for (const row of allRows) {
      if (row.depth >= 1 && row.hasChildren) initial.add(row.span.spanId)
    }
    setCollapsed(initial)
  }, [traceId])

  // Filter out descendants of collapsed spans
  const rows = useMemo(() => {
    const hidden = new Set<string>()
    for (const row of allRows) {
      if (collapsed.has(row.span.spanId)) {
        // Collect all descendant spanIds. Copy the tree's child array — pop()
        // below would otherwise mutate it in place, emptying tree.get(spanId)
        // for every consumer downstream in the same render (articleRowStatus's
        // findStageSpans call, notably, which would then see no stage spans and
        // report every collapsed article row as 'ok').
        const stack = [...(tree.get(row.span.spanId) ?? [])]
        while (stack.length) {
          const child = stack.pop()!
          hidden.add(child.spanId)
          stack.push(...(tree.get(child.spanId) ?? []))
        }
      }
    }
    return allRows.filter(r => !hidden.has(r.span.spanId))
  }, [allRows, collapsed, tree])

  const root = spans.find(s => !s.parentSpanId || s.parentSpanId === '')
  const rootStart      = root ? BigInt(root.startTimeUnixNano) : 0n
  const rootDurationNs = root ? BigInt(root.endTimeUnixNano) - BigInt(root.startTimeUnixNano) : 0n

  const environment = getResourceAttr(trace, 'deployment.environment')
    ?? getResourceAttr(trace, 'resource.deployment.environment')
  const traceServiceName = getResourceAttr(trace, 'service.name')
  const isBackendTrace = traceServiceName === SERVICE_NAME_BACKEND
  const isScraperTrace = traceServiceName === SERVICE_NAME
  // Both apps are profiled as of fix/profiler_imprv (previously backend-only) — resolves
  // which pyroscope.configure(application_name=...) to query (backend/routers/grafana.py's
  // `service` param) for whichever kind of trace this is.
  const isProfiledTrace = isBackendTrace || isScraperTrace
  const profileService: 'backend' | 'scraper' = isBackendTrace ? 'backend' : 'scraper'

  const startDate = root
    ? new Date(Number(rootStart / 1_000_000n)).toLocaleString()
    : '—'
  // unix seconds — Pyroscope's render API (backend/routers/grafana.py's /profile) takes
  // start/end in seconds, not nanoseconds like the span timestamps here.
  //
  // Padded by FLAME_GRAPH_PADDING_SECONDS on both sides rather than using the request's
  // own [start, end]: pyroscope-io uploads sampled profiles periodically (not one batch
  // per request), and almost every request span is well under a second — dividing two
  // sub-second nanosecond timestamps down to whole seconds collapses start and end to the
  // *same* second for virtually every request, producing a zero-width from==until query
  // Pyroscope has nothing to return for (confirmed: this is exactly what was happening —
  // a real 12ms request produced start=1789896395&end=1789896395).
  //
  // 10s, not some much larger value — swept 0/1/2/3/5/8/10/12/15/20/30s against a real
  // pushed profile: any non-zero width already returns data (the zero-width case is the
  // only one that's actually empty), and pyroscope.configure()'s upload_interval default
  // is 10s (backend/observability.py never overrides it), so ±10s (20s total) is the
  // smallest padding that's still reliably wider than one full upload interval regardless
  // of where the request falls inside it. Wider padding pulls in more samples (and a
  // richer flame graph) but increasingly reflects "what the process was doing in this
  // minute" rather than this specific request — 10s favors staying close to the request
  // over sample density.
  const FLAME_GRAPH_PADDING_SECONDS = 10
  const flameGraphStart = root
    ? Math.floor(Number(rootStart / 1_000_000_000n)) - FLAME_GRAPH_PADDING_SECONDS
    : 0
  const flameGraphEnd = root
    ? Math.floor(Number((rootStart + rootDurationNs) / 1_000_000_000n)) + FLAME_GRAPH_PADDING_SECONDS
    : 0

  // Best-effort — a failed/unconfigured fetch just leaves the strip absent (CpuUtilizationStrip
  // renders nothing for an empty bars array), same graceful-degradation contract every other
  // profiling touchpoint in this codebase already has.
  useEffect(() => {
    if (!open || !isProfiledTrace || !root) return
    let cancelled = false
    queryProfile({ start: flameGraphStart, end: flameGraphEnd, service: profileService })
      .then(res => {
        if (cancelled || 'error' in res) return
        setProfileTimeline(res.timeline ?? null)
        setProfileSampleRate(res.metadata?.sampleRate || 1)
      })
      .catch(() => {})
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isProfiledTrace, profileService, traceId])

  // Plain derived value, not useMemo — matches flame-graph-dialog.tsx's own `frames`
  // (layoutFlamebearer's result), a similarly cheap per-render recompute over a small array.
  const overlayBars = profileTimeline
    ? timelineToOverlayBars(profileTimeline, profileSampleRate, rootStart, rootDurationNs)
    : []

  function toggle(spanId: string) {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(spanId)) {
        next.delete(spanId)
      } else {
        next.add(spanId)
      }
      return next
    })
  }

  return (
    <>
    <FlameGraphDialog
      open={showFlameGraph}
      onClose={() => { setShowFlameGraph(false); setFlameGraphSpanId(undefined) }}
      start={flameGraphStart}
      end={flameGraphEnd}
      service={profileService}
      spanId={flameGraphSpanId}
    />
    {selectedSpan && (
      <Dialog open onOpenChange={v => { if (!v) setSelectedSpan(null) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">
              {selectedSpan.name.split('.').slice(-2).join('.')}
            </DialogTitle>
          </DialogHeader>
          <StageCard
            span={selectedSpan}
            className="w-full"
            onViewProfile={isProfiledTrace ? () => {
              setFlameGraphSpanId(selectedSpan.spanId)
              setShowFlameGraph(true)
            } : undefined}
          />
        </DialogContent>
      </Dialog>
    )}
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-[90vw] sm:max-w-[90vw] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <div className="flex items-start justify-between gap-3 pr-6">
            <div>
              <DialogTitle className="font-mono text-sm">
                {t('admin.waterfallDialogTitle', { id: traceId.slice(0, 16) })}
              </DialogTitle>
              <p className="text-xs text-muted-foreground">
                {startDate}
                {root && <> · {formatDuration(spanDurationMs(root))}</>}
                {environment && <> · {environment}</>}
              </p>
            </div>
            {isProfiledTrace && root && (
              <button
                onClick={() => { setFlameGraphSpanId(undefined); setShowFlameGraph(true) }}
                className="shrink-0 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-border text-muted-foreground hover:border-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                <Activity className="h-3 w-3" />
                {t('admin.viewProfile')}
              </button>
            )}
          </div>
        </DialogHeader>

        <div className="themed-scrollbar overflow-auto flex-1 min-h-0">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0 bg-background border-b border-border">
              <tr>
                <th className="text-left py-1.5 pr-4 font-medium text-muted-foreground w-[40%]">{t('admin.waterfallColumnSpan')}</th>
                <th className="text-right py-1.5 px-4 font-medium text-muted-foreground w-20">{t('admin.traceColumnDuration')}</th>
                <th className="text-left py-1.5 pl-2 font-medium text-muted-foreground">{t('admin.waterfallColumnTimeline')}</th>
              </tr>
              {/* CPU-utilization strip, aligned to the same rootStart/rootDurationNs coordinate
                  space every SpanBar row below uses — so "was the CPU actually busy here" can
                  be read directly against the span gaps beneath it, not just guessed from them.
                  Absent entirely (not just empty) whenever profiling isn't configured or this
                  window has no samples — overlayBars is [] in both cases. */}
              {overlayBars.length > 0 && (
                <tr className="border-b border-border/50">
                  <th className="text-left py-1 pr-4 font-normal text-[10px] text-muted-foreground w-[40%]">
                    {t('admin.waterfallCpuRowLabel')}
                  </th>
                  <th className="py-1 px-4 w-20" />
                  <th className="text-left py-1 pl-2 font-normal">
                    <CpuUtilizationStrip bars={overlayBars} />
                  </th>
                </tr>
              )}
            </thead>
            <tbody>
              {rows.map(({ span, depth, hasChildren }) => {
                const isPipeline = span.name === SpanName.ARTICLE_PIPELINE
                const isTopic = span.name === SpanName.WEEKLY_REPORT_TOPIC
                const isDiscoverTask = span.name === SpanName.DISCOVER_TASK
                const durationMs = spanDurationMs(span)
                const error = isErrorSpan(span)
                // For an article.pipeline row: roll up its stage spans so a
                // downstream-only failure (analysis/translate/RAG) shows as
                // partial (▲) rather than looking clean.
                const pipelineStatus = isPipeline
                  ? articleRowStatus(span, findStageSpans(tree, span.spanId))
                  : null
                const isCollapsed = collapsed.has(span.spanId)
                const methodSpan = !isPipeline && !isTopic && !isDiscoverTask ? splitMethodSpanName(span.name) : null
                const dbSystem = !isPipeline && !isTopic && !isDiscoverTask ? (getAttr(span, 'db.system') as string | undefined) : undefined
                const label = isPipeline
                  ? `↳ ${(getAttr(span, 'article.url') as string | undefined)?.split('/').slice(-2).join('/') ?? 'article'}`
                  : isTopic
                  ? `↳ ${(getAttr(span, 'topic.name') as string | undefined) ?? 'topic'}`
                  : isDiscoverTask
                  ? `↳ ${(getAttr(span, 'discover.source') as string | undefined) ?? 'source'}`
                  : methodSpan
                  ? methodSpan.path
                  : span.name.split('.').slice(-2).join('.')
                const isClickable = isPipeline ? !!onSelectArticle : isTopic ? !!onSelectTopic : true

                return (
                  <tr
                    key={span.spanId}
                    className={cn(
                      'border-b border-border/30 hover:bg-muted/20 transition-colors',
                      isClickable && 'cursor-pointer',
                    )}
                    onClick={() => {
                      if (isPipeline && onSelectArticle) {
                        onSelectArticle(span, findStageSpans(tree, span.spanId))
                      } else if (isTopic && onSelectTopic) {
                        onSelectTopic(span, findStageSpans(tree, span.spanId))
                      } else if (!isPipeline && !isTopic) {
                        setSelectedSpan(span)
                      }
                    }}
                  >
                    <td
                      className={cn(
                        'py-1 pr-4 truncate max-w-0',
                        (error || pipelineStatus === 'failed') && 'text-destructive',
                      )}
                      style={{ paddingLeft: `${depth * 14 + 6}px` }}
                    >
                      <span className="inline-flex items-center gap-0.5">
                        {hasChildren && (
                          <button
                            onClick={e => { e.stopPropagation(); toggle(span.spanId) }}
                            className="text-muted-foreground hover:text-foreground transition-colors mr-0.5 cursor-pointer"
                            aria-label={isCollapsed ? 'Expand' : 'Collapse'}
                          >
                            {isCollapsed
                              ? <ChevronRight className="h-3 w-3" />
                              : <ChevronDown className="h-3 w-3" />
                            }
                          </button>
                        )}
                        {!hasChildren && <span className="inline-block w-3.5" />}
                        {methodSpan && <HttpMethodBadge method={methodSpan.method} />}
                        {dbSystem && <DbSystemBadge system={dbSystem} />}
                        {label}
                        {pipelineStatus === 'failed' && (
                          <span className="text-destructive ml-1" title={t('admin.articleStatusFailed')}>✗</span>
                        )}
                        {pipelineStatus === 'partial' && (
                          <span className="text-amber-500 ml-1" title={t('admin.articleStatusPartial')}>▲</span>
                        )}
                      </span>
                    </td>
                    <td className="py-1 px-4 text-right tabular-nums text-muted-foreground whitespace-nowrap">
                      {formatDuration(durationMs)}
                    </td>
                    <td className="py-1 pl-2 w-[45%]">
                      <SpanBar span={span} rootStart={rootStart} rootDurationNs={rootDurationNs} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
    </>
  )
}