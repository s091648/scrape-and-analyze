'use client'

import { cn } from '@/lib/utils'
import type { OtlpSpan, OtlpAttributeValue } from '@/lib/api/grafana'
import { spanDurationMs, isErrorSpan, formatDuration } from '@/lib/otlp-utils'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const STAGE_LABELS: Record<string, string> = {
  'article.scraped.handle':           'Scraped',
  'article.processed.handle':         'Processed',
  'article.tag_normalization.handle': 'Tag Norm',
  'article.analysis_completed.handle':'Analysis Done',
}

function formatValue(v: OtlpAttributeValue): string {
  if (v.boolValue !== undefined) return v.boolValue ? '✓' : '✗'
  if (v.intValue !== undefined)  return parseInt(v.intValue, 10).toLocaleString()
  if (v.doubleValue !== undefined) return v.doubleValue.toFixed(3)
  const s = v.stringValue ?? '—'
  return s.length > 60 ? `${s.slice(0, 57)}…` : s
}

interface StageCardProps {
  span: OtlpSpan
}

export function StageCard({ span }: StageCardProps) {
  const durationMs = spanDurationMs(span)
  const error = isErrorSpan(span)
  const label = STAGE_LABELS[span.name] ?? span.name.split('.').pop() ?? span.name

  return (
    <div className={cn(
      'rounded-lg border bg-card p-3 min-w-[160px] max-w-[240px] flex-shrink-0 flex flex-col gap-1.5',
      error ? 'border-destructive' : 'border-border',
    )}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <span className={cn('font-semibold text-sm truncate', error && 'text-destructive')}>
          {label}
        </span>
        <span className={cn('text-xs shrink-0', error ? 'text-destructive' : 'text-muted-foreground')}>
          {error ? '✗' : '✓'}
        </span>
      </div>

      {/* Duration */}
      <p className="text-xs text-muted-foreground">{formatDuration(durationMs)}</p>

      {/* Attributes */}
      {span.attributes.length > 0 && (
        <div className="border-t border-border pt-1.5 space-y-1">
          {span.attributes.map(attr => (
            <Tooltip key={attr.key}>
              <TooltipTrigger asChild>
                <div className="text-xs flex gap-1 items-start cursor-default">
                  <span className="text-muted-foreground shrink-0 truncate max-w-[90px]">
                    {attr.key.split('.').pop()}:
                  </span>
                  <span className="font-mono break-all line-clamp-2">
                    {formatValue(attr.value)}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs font-mono text-xs break-all">
                <p className="font-semibold text-muted-foreground">{attr.key}</p>
                <p>{formatValue(attr.value)}</p>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      )}

      {/* Error message from span status */}
      {error && span.status?.message && (
        <p className="text-xs text-destructive break-words border-t border-destructive/30 pt-1.5">
          {span.status.message}
        </p>
      )}
    </div>
  )
}