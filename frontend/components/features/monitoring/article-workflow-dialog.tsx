'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { OtlpSpan } from '@/lib/api/grafana'
import { getAttr, spanDurationMs, formatDuration } from '@/lib/otlp-utils'
import { StageCard } from './stage-card'

interface ArticleWorkflowDialogProps {
  open: boolean
  onClose: () => void
  pipelineSpan: OtlpSpan
  stageSpans: OtlpSpan[]
}

export function ArticleWorkflowDialog({
  open,
  onClose,
  pipelineSpan,
  stageSpans,
}: ArticleWorkflowDialogProps) {
  const url    = getAttr(pipelineSpan, 'article.url') as string | undefined
  const source = getAttr(pipelineSpan, 'article.source') as string | undefined
  const totalMs = spanDurationMs(pipelineSpan)

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm font-mono truncate">
            {url ?? 'Article Pipeline'}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {formatDuration(totalMs)}
            {source && <> · source: <span className="font-mono">{source}</span></>}
          </p>
        </DialogHeader>

        <TooltipProvider>
          <div className="overflow-auto pb-2">
            {/* Horizontal workflow on medium+ screens, wraps on small */}
            <div className="flex items-start gap-2 flex-wrap md:flex-nowrap min-w-max">
              {stageSpans.map((span, i) => (
                <div key={span.spanId} className="flex items-center gap-2">
                  <StageCard span={span} />
                  {i < stageSpans.length - 1 && (
                    <span className="text-muted-foreground text-base self-start mt-4 shrink-0">
                      →
                    </span>
                  )}
                </div>
              ))}
              {stageSpans.length === 0 && (
                <p className="text-sm text-muted-foreground py-4">
                  No stage spans found for this article.
                </p>
              )}
            </div>
          </div>
        </TooltipProvider>
      </DialogContent>
    </Dialog>
  )
}