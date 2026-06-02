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
  return { p70: at(0.70), p80: at(0.80), p90: at(0.90) }
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
          {/* Vertical workflow layout */}
          <div className="flex flex-col items-stretch">
            {stageSpans.map((node, i) => (
              <div key={node.span.spanId} className="flex flex-col items-center" style={{ paddingLeft: node.depth * 24 }}>
                <StageCard span={node.span} className="w-full" thresholds={percentileMap.get(node.span.name)} />
                {i < stageSpans.length - 1 && (
                  <ArrowDown className="h-5 w-5 text-muted-foreground/60 my-0.5 shrink-0" strokeWidth={2.5} />
                )}
              </div>
            ))}
            {stageSpans.length === 0 && (
              <p className="text-sm text-muted-foreground py-4">
                {t('admin.articlePipelineNoStages')}
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
