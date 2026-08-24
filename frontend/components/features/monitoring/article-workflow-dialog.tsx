'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ArrowDown } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import type { OtlpSpan } from '@/lib/api/grafana'
import { queryTracesBatch, queryLogs, type LokiStreamResult } from '@/lib/api/grafana'
import type { SpanNode } from '@/lib/otlp-utils'
import { getAttr, spanDurationMs, formatDuration, otlpIdToHex } from '@/lib/otlp-utils'
import { lokiStreamSelector } from '@/lib/observability-constants'
import { StageCard, type SpanPercentileThresholds } from './stage-card'
import { LogDetailDialog, type LogEntry } from './log-detail-dialog'

interface ArticleWorkflowDialogProps {
  open: boolean
  onClose: () => void
  pipelineSpan: OtlpSpan
  stageSpans: SpanNode[]
  /** When set, the matching span card will be highlighted with a ring. */
  highlightedSpanId?: string
}

function computeThresholds(durations: number[]): SpanPercentileThresholds {
  const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length
  return { avg, count: durations.length, durations }
}

function getLabelOverride(span: OtlpSpan, t: (k: string, p?: Record<string, string | number>) => string): string | undefined {
  if (span.name === 'article.translate.handle') {
    const lang = getAttr(span, 'translation.language')
    if (lang) return t('admin.stageTranslateLabel', { lang: String(lang) })
  }
  return undefined
}

/** Query Loki for logs matching a specific trace + span, return most recent entry. */
async function fetchSpanLog(span: OtlpSpan): Promise<LogEntry | null> {
  const traceIdHex = otlpIdToHex(span.traceId)
  const spanIdHex  = otlpIdToHex(span.spanId)
  const bufNs = 60_000_000_000n  // 1 minute buffer in nanoseconds
  const startNs = String(BigInt(span.startTimeUnixNano) - bufNs)
  const endNs   = String(BigInt(span.endTimeUnixNano)   + bufNs)
  const query   = `${lokiStreamSelector()} | json | trace_id = "${traceIdHex}" | span_id = "${spanIdHex}"`
  try {
    const res = await queryLogs({ query, start: startNs, end: endNs, limit: 10 })
    if (res.status !== 'success' || !res.data?.result.length) return null
    const streams = res.data.result as LokiStreamResult[]
    // Flatten and pick most recent
    const all: Array<{ ms: number; line: string; env?: string }> = []
    for (const stream of streams) {
      for (const [tsNs, line] of stream.values) {
        all.push({ ms: Math.floor(Number(tsNs) / 1_000_000), line, env: stream.stream['env'] })
      }
    }
    if (all.length === 0) return null
    all.sort((a, b) => b.ms - a.ms)
    const { ms, line, env } = all[0]
    let level = 'info'
    let message = line
    try {
      const obj = JSON.parse(line)
      level   = String(obj.level ?? obj.severity ?? 'info').toLowerCase()
      message = String(obj.event ?? obj.message ?? obj.msg ?? line)
    } catch { /* not JSON */ }
    return {
      ts: new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
      tsExact: new Date(ms).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      level, env, message, raw: line,
    }
  } catch { return null }
}

export function ArticleWorkflowDialog({
  open,
  onClose,
  pipelineSpan,
  stageSpans,
  highlightedSpanId,
}: ArticleWorkflowDialogProps) {
  const { t } = useI18n()
  const url    = getAttr(pipelineSpan, 'article.url') as string | undefined
  const source = getAttr(pipelineSpan, 'article.source') as string | undefined
  const totalMs = spanDurationMs(pipelineSpan)

  // article.title lives on the article.processed.handle child span
  const title = stageSpans
    .map(n => getAttr(n.span, 'article.title'))
    .find(v => v !== undefined) as string | undefined

  const [percentileMap, setPercentileMap] = useState<Map<string, SpanPercentileThresholds>>(new Map())
  // Empty set = all expanded (default B: expanded)
  const [collapsedSpans, setCollapsedSpans] = useState<Set<string>>(new Set())
  const [logEntry, setLogEntry] = useState<LogEntry | null>(null)
  const highlightedRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Scroll to highlighted span after dialog fully renders.
  // Uses manual container scroll instead of scrollIntoView because the dialog
  // overflow container is fixed-position and scrollIntoView may scroll the viewport.
  const scrollToHighlighted = useCallback(() => {
    const el = highlightedRef.current
    const container = scrollContainerRef.current
    if (!el || !container) return
    const elRect = el.getBoundingClientRect()
    const containerRect = container.getBoundingClientRect()
    const offset = elRect.top - containerRect.top - (containerRect.height - elRect.height) / 2
    container.scrollBy({ top: offset, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (!open || !highlightedSpanId) return
    // Wait for dialog open animation + layout before scrolling
    const timer = setTimeout(scrollToHighlighted, 400)
    return () => clearTimeout(timer)
  }, [open, highlightedSpanId, scrollToHighlighted])

  async function handleViewLogs(span: OtlpSpan) {
    const entry = await fetchSpanLog(span)
    setLogEntry(entry ?? {
      ts: '', tsExact: '', level: 'info', message: 'No logs found for this span.', raw: '',
    })
  }

  function toggleCollapse(spanId: string) {
    setCollapsedSpans(prev => {
      const next = new Set(prev)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  useEffect(() => {
    if (!open || stageSpans.length === 0) return
    let cancelled = false
    const spanNames = [...new Set(stageSpans.map(n => n.span.name))]
    const now = Math.floor(Date.now() / 1000)
    const queries = spanNames.map(name => ({
      q: `{ name="${name}" }`,
      start: now - 7 * 86400,
      end: now,
      limit: 200,
    }))
    queryTracesBatch(queries).then(responses => {
      if (cancelled) return
      const map = new Map<string, SpanPercentileThresholds>()
      responses.forEach((res, i) => {
        const durations: number[] = []
        for (const trace of res.traces ?? []) {
          const spanSets = trace.spanSets ?? (trace.spanSet ? [trace.spanSet] : [])
          for (const ss of spanSets) {
            for (const s of ss.spans ?? []) {
              if (s.durationNanos) durations.push(Number(BigInt(s.durationNanos) / 1_000_000n))
            }
          }
        }
        if (durations.length >= 5) map.set(spanNames[i], computeThresholds(durations))
      })
      setPercentileMap(map)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [open, stageSpans])

  // Build parent → children map for depth > 0 spans
  const topLevel = stageSpans.filter(n => n.depth === 0)
  const childMap = new Map<string, SpanNode[]>()
  for (const node of stageSpans) {
    if (node.depth > 0 && node.span.parentSpanId) {
      if (!childMap.has(node.span.parentSpanId)) childMap.set(node.span.parentSpanId, [])
      childMap.get(node.span.parentSpanId)!.push(node)
    }
  }

  return (
    <>
    <LogDetailDialog entry={logEntry} onClose={() => setLogEntry(null)} />
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-[90vw] sm:max-w-[90vw] w-full max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-sm truncate">
            {title ?? url ?? t('admin.articlePipelineTitle')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {formatDuration(totalMs)}
            {source && <> · {t('admin.articlePipelineSource')}: <span className="font-mono">{source}</span></>}
          </p>
        </DialogHeader>

        <div ref={scrollContainerRef} className="themed-scrollbar overflow-auto flex-1 min-h-0 pb-2">
          <div className="flex flex-col items-stretch">
            {stageSpans.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">
                {t('admin.articlePipelineNoStages')}
              </p>
            ) : (
              topLevel.map((node, i) => {
                const children = childMap.get(node.span.spanId) ?? []
                const hasChildren = children.length > 0
                const isCollapsed = collapsedSpans.has(node.span.spanId)
                const isLast = i === topLevel.length - 1
                const isNodeHighlighted = !!highlightedSpanId && otlpIdToHex(node.span.spanId) === highlightedSpanId

                return (
                  <div
                    key={node.span.spanId}
                    className="flex flex-col items-center"
                    ref={isNodeHighlighted ? highlightedRef : undefined}
                  >
                    {/* Top-level stage card */}
                    <StageCard
                      span={node.span}
                      className="w-full"
                      thresholds={percentileMap.get(node.span.name)}
                      collapsed={hasChildren ? isCollapsed : undefined}
                      onToggleCollapse={hasChildren ? () => toggleCollapse(node.span.spanId) : undefined}
                      isHighlighted={isNodeHighlighted}
                      onViewLogs={() => handleViewLogs(node.span)}
                    />

                    {/* Child spans (e.g. Translate jobs under Analysis Done) */}
                    {hasChildren && !isCollapsed && (
                      <div className="w-full ml-6 mt-1 pl-3 border-l-2 border-muted-foreground/25 space-y-1">
                        {children.map((child, ci) => {
                          const isChildHighlighted = !!highlightedSpanId && otlpIdToHex(child.span.spanId) === highlightedSpanId
                          return (
                            <div
                              key={child.span.spanId}
                              className="flex flex-col items-start"
                              ref={isChildHighlighted ? highlightedRef : undefined}
                            >
                              <StageCard
                                span={child.span}
                                className="w-full"
                                thresholds={percentileMap.get(child.span.name)}
                                labelOverride={getLabelOverride(child.span, t)}
                                isHighlighted={isChildHighlighted}
                                onViewLogs={() => handleViewLogs(child.span)}
                              />
                              {ci < children.length - 1 && (
                                <ArrowDown className="h-3.5 w-3.5 text-muted-foreground/40 my-0.5 ml-4 shrink-0" strokeWidth={2} />
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}

                    {/* Arrow between top-level stages only */}
                    {!isLast && (
                      <ArrowDown className="h-5 w-5 text-muted-foreground/60 my-0.5 shrink-0" strokeWidth={2.5} />
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
    </>
  )
}
