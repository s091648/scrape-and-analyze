'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
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
  const { t } = useI18n()
  const url    = getAttr(pipelineSpan, 'article.url') as string | undefined
  const source = getAttr(pipelineSpan, 'article.source') as string | undefined
  const totalMs = spanDurationMs(pipelineSpan)

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
            {stageSpans.map((span, i) => (
              <div key={span.spanId} className="flex flex-col items-center">
                <StageCard span={span} className="w-full" />
                {i < stageSpans.length - 1 && (
                  <span className="text-muted-foreground text-base shrink-0 my-0.5">
                    ↓
                  </span>
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