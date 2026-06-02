'use client'

import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ArrowDown } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import type { OtlpSpan } from '@/lib/api/grafana'
import { queryTracesBatch } from '@/lib/api/grafana'
import type { SpanNode } from '@/lib/otlp-utils'
import { getAttr, spanDurationMs, formatDuration } from '@/lib/otlp-utils'
import { StageCard, type SpanPercentileThresholds } from './stage-card'

interface ArticleWorkflowDialogProps {
  open: boolean
  onClose: () => void
  pipelineSpan: OtlpSpan
  stageSpans: SpanNode[]
}

function computeThresholds(durations: number[]): SpanPercentileThresholds {
  const sorted = [...durations].sort((a, b) => a - b)
  const at = (p: number) => sorted[Math.floor(sorted.length * p)] ?? Infinity
  const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length
  return {
    p50: at(0.50),
    p70: at(0.70),
    p80: at(0.80),
    p90: at(0.90),
    avg,
    count: durations.length,
  }
}

function getLabelOverride(span: OtlpSpan): string | undefined {
  if (span.name === 'article.translate.handle') {
    const lang = getAttr(span, 'translation.language')
    if (lang) return `Translate (${String(lang)})`
  }
  return undefined
}

export function ArticleWorkflowDialog({
  open,
  onClose,
  pipelineSpan,
  stageSpans,
}: ArticleWorkflowDialogProps) {
  const { t } = useI18n()
  const url    = getAttr(pipelineSpan, 'article.url') as string | undefined
  const source = getAttr(pipelineSpan, 'article.source') as string | undefined
  const totalMs = spanDurationMs(pipelineSpan)

  const [percentileMap, setPercentileMap] = useState<Map<string, SpanPercentileThresholds>>(new Map())
  // Empty set = all expanded (default B: expanded)
  const [collapsedSpans, setCollapsedSpans] = useState<Set<string>>(new Set())

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
    const spanNames = [...new Set(stageSpans.map(n => n.span.name))]
    const now = Math.floor(Date.now() / 1000)
    const queries = spanNames.map(name => ({
      q: `{ name="${name}" }`,
      start: now - 7 * 86400,
      end: now,
      limit: 200,
    }))
    queryTracesBatch(queries).then(responses => {
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
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-3xl w-full max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm font-mono truncate">
            {url ?? t('admin.articlePipelineTitle')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {formatDuration(totalMs)}
            {source && <> · {t('admin.articlePipelineSource')}: <span className="font-mono">{source}</span></>}
          </p>
        </DialogHeader>

        <div className="overflow-auto flex-1 pb-2">
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

                return (
                  <div key={node.span.spanId} className="flex flex-col items-center">
                    {/* Top-level stage card */}
                    <StageCard
                      span={node.span}
                      className="w-full"
                      thresholds={percentileMap.get(node.span.name)}
                      collapsed={hasChildren ? isCollapsed : undefined}
                      onToggleCollapse={hasChildren ? () => toggleCollapse(node.span.spanId) : undefined}
                    />

                    {/* Child spans (e.g. Translate jobs under Analysis Done) */}
                    {hasChildren && !isCollapsed && (
                      <div className="w-full ml-6 mt-1 pl-3 border-l-2 border-muted-foreground/25 space-y-1">
                        {children.map((child, ci) => (
                          <div key={child.span.spanId} className="flex flex-col items-start">
                            <StageCard
                              span={child.span}
                              className="w-full"
                              thresholds={percentileMap.get(child.span.name)}
                              labelOverride={getLabelOverride(child.span)}
                            />
                            {ci < children.length - 1 && (
                              <ArrowDown className="h-3.5 w-3.5 text-muted-foreground/40 my-0.5 ml-4 shrink-0" strokeWidth={2} />
                            )}
                          </div>
                        ))}
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
  )
}
