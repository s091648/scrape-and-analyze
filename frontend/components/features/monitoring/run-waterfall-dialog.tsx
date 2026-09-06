'use client'

import { useState, useMemo, useEffect } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
import type { OtlpTraceResponse, OtlpSpan } from '@/lib/api/grafana'
import {
  flattenSpans, buildSpanTree, spanDurationMs, isErrorSpan,
  getAttr, getResourceAttr, findStageSpans, formatDuration, articleRowStatus,
  type SpanNode,
} from '@/lib/otlp-utils'
import { SpanName } from '@/lib/observability-constants'
import { StageCard } from './stage-card'
import { HttpMethodBadge, splitMethodSpanName, DbSystemBadge } from './log-detail-dialog'
import { cn } from '@/lib/utils'

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

  const startDate = root
    ? new Date(Number(rootStart / 1_000_000n)).toLocaleString()
    : '—'

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
    {selectedSpan && (
      <Dialog open onOpenChange={v => { if (!v) setSelectedSpan(null) }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">
              {selectedSpan.name.split('.').slice(-2).join('.')}
            </DialogTitle>
          </DialogHeader>
          <StageCard span={selectedSpan} className="w-full" />
        </DialogContent>
      </Dialog>
    )}
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-[90vw] sm:max-w-[90vw] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">
            {t('admin.waterfallDialogTitle', { id: traceId.slice(0, 16) })}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {startDate}
            {root && <> · {formatDuration(spanDurationMs(root))}</>}
            {environment && <> · {environment}</>}
          </p>
        </DialogHeader>

        <div className="themed-scrollbar overflow-auto flex-1 min-h-0">
          <table className="w-full text-xs border-collapse">
            <thead className="sticky top-0 bg-background border-b border-border">
              <tr>
                <th className="text-left py-1.5 pr-4 font-medium text-muted-foreground w-[40%]">{t('admin.waterfallColumnSpan')}</th>
                <th className="text-right py-1.5 px-4 font-medium text-muted-foreground w-20">{t('admin.traceColumnDuration')}</th>
                <th className="text-left py-1.5 pl-2 font-medium text-muted-foreground">{t('admin.waterfallColumnTimeline')}</th>
              </tr>
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