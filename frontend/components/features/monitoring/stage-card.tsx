'use client'

import { cn } from '@/lib/utils'
import { ChevronRight, ChevronDown } from 'lucide-react'
import type { OtlpSpan, OtlpAttributeValue } from '@/lib/api/grafana'
import { spanDurationMs, isErrorSpan, formatDuration } from '@/lib/otlp-utils'
import { useI18n } from '@/lib/providers'
import {
  Tooltip as RadixTooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'

const STAGE_I18N_KEYS: Record<string, string> = {
  'article.scraped.handle':                'admin.stageLabel_scraped',
  'article.processed.handle':              'admin.stageLabel_processed',
  'article.tag_normalization.handle':      'admin.stageLabel_tagNorm',
  'article.analysis_completed.handle':     'admin.stageLabel_analysisDone',
  'article.translate.handle':              'admin.stageLabel_translate',
  'article.analysis_failed.handle':         'admin.stageLabel_analysisFailed',
  'article.tag_normalization_failed.handle': 'admin.stageLabel_tagNormFailed',
  'article.translation_failed.handle':     'admin.stageLabel_translationFailed',
  'scraper.pipeline_completed.handle':      'admin.stageLabel_pipelineCompleted',
  'scraper.pipeline_completed.notify':      'admin.stageLabel_pipelineNotify',
}

const ATTR_I18N_KEYS: Record<string, string> = {
  'article.id':                    'admin.stageAttr_articleId',
  'article.title':                 'admin.stageAttr_articleTitle',
  'article.url':                   'admin.stageAttr_url',
  'article.source':                'admin.stageAttr_source',
  'article.topic_id':              'admin.stageAttr_topicId',
  'article.topic_display_name':    'admin.stageAttr_topicName',
  'article.content_chars':         'admin.stageAttr_contentChars',
  'article.outcome':               'admin.stageAttr_outcome',
  'analysis.id':                   'admin.stageAttr_analysisId',
  'analysis.success':              'admin.stageAttr_success',
  'analysis.error_type':           'admin.stageAttr_errorType',
  'llm.model':                     'admin.stageAttr_llmModel',
  'llm.input_tokens':              'admin.stageAttr_inputTokens',
  'llm.output_tokens':             'admin.stageAttr_outputTokens',
  'tags.group_count':              'admin.stageAttr_tagGroups',
  'tags.group_names':              'admin.stageAttr_tagGroupNames',
  'tags.total_count':              'admin.stageAttr_totalTags',
  'tags.tag_names':                'admin.stageAttr_tagNames',
  'normalization.success':         'admin.stageAttr_normSuccess',
  'normalization.error_type':      'admin.stageAttr_normErrorType',
  'translation.target_languages':  'admin.stageAttr_targetLangs',
  'translation.language':          'admin.stageAttr_language',
  'translation.success':           'admin.stageAttr_translationSuccess',
  'translation.error_type':        'admin.stageAttr_translationErrorType',
  'task.type':                     'admin.stageAttr_taskType',
  'task.exception_type':           'admin.stageAttr_exceptionType',
  'pipeline.duration_seconds':     'admin.stageAttr_pipelineDuration',
  'pipeline.sources_count':        'admin.stageAttr_pipelineSourcesCount',
  'sources.count':                 'admin.stageAttr_sourcesCount',
  'articles.discovered':           'admin.stageAttr_articlesDiscovered',
  'articles.before_dedup':         'admin.stageAttr_articlesBeforeDedup',
  'articles.after_dedup':          'admin.stageAttr_articlesAfterDedup',
  'articles.skipped':              'admin.stageAttr_articlesSkipped',
  'articles.published':            'admin.stageAttr_articlesPublished',
}

function formatValue(v: OtlpAttributeValue): string {
  if (v.boolValue !== undefined) return v.boolValue ? '✓' : '✗'
  if (v.intValue !== undefined)  return parseInt(v.intValue, 10).toLocaleString()
  if (v.doubleValue !== undefined) return v.doubleValue.toFixed(3)
  if ((v as { arrayValue?: { values?: OtlpAttributeValue[] } }).arrayValue?.values) {
    return (v as { arrayValue: { values: OtlpAttributeValue[] } }).arrayValue.values
      .map(item => item.stringValue ?? item.intValue ?? '')
      .filter(Boolean)
      .join(', ')
  }
  const s = v.stringValue ?? '—'
  return s.length > 60 ? `${s.slice(0, 57)}…` : s
}

export interface SpanPercentileThresholds {
  p50: number
  p70: number
  p80: number
  p90: number
  avg: number
  count: number
}

interface StageCardProps {
  span: OtlpSpan
  className?: string
  thresholds?: SpanPercentileThresholds
  labelOverride?: string
  collapsed?: boolean
  onToggleCollapse?: () => void
}

function durationColor(ms: number, thresholds?: SpanPercentileThresholds): string {
  if (!thresholds) return 'text-foreground'
  if (ms >= thresholds.p90) return 'text-red-500'
  if (ms >= thresholds.p80) return 'text-orange-600'
  if (ms >= thresholds.p70) return 'text-orange-400'
  return 'text-foreground'
}

export function StageCard({ span, className, thresholds, labelOverride, collapsed, onToggleCollapse }: StageCardProps) {
  const { t } = useI18n()
  const durationMs = spanDurationMs(span)
  const error = isErrorSpan(span)
  const stageI18nKey = STAGE_I18N_KEYS[span.name]
  const label = labelOverride ?? (stageI18nKey ? t(stageI18nKey) : (span.name.split('.').pop() ?? span.name))

  const durationBadge = thresholds && thresholds.count >= 5 ? (
    <RadixTooltip>
      <TooltipTrigger asChild>
        <span className={cn('text-sm font-semibold shrink-0 cursor-default', durationColor(durationMs, thresholds))}>
          {formatDuration(durationMs)}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs space-y-0.5">
        <p>Avg: {formatDuration(thresholds.avg)} · P50: {formatDuration(thresholds.p50)}</p>
        <p>P70: {formatDuration(thresholds.p70)} · P80: {formatDuration(thresholds.p80)} · P90: {formatDuration(thresholds.p90)}</p>
        <p className="text-muted-foreground">n={thresholds.count} · last 7d</p>
      </TooltipContent>
    </RadixTooltip>
  ) : (
    <span className={cn('text-sm font-semibold shrink-0', durationColor(durationMs, thresholds))}>
      {formatDuration(durationMs)}
    </span>
  )

  return (
    <div className={cn(
      'rounded-lg border-2 bg-card p-3 min-w-[160px] flex-shrink-0 flex flex-col gap-1.5',
      error ? 'border-destructive' : 'border-emerald-500',
      className,
    )}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1 min-w-0">
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={collapsed ? 'Expand' : 'Collapse'}
            >
              {collapsed
                ? <ChevronRight className="h-3.5 w-3.5" />
                : <ChevronDown className="h-3.5 w-3.5" />
              }
            </button>
          )}
          <span className={cn('font-semibold text-sm truncate', error && 'text-destructive')}>
            {label}
          </span>
        </div>
        {durationBadge}
      </div>

      {/* Error label — OK is communicated by green outline */}
      {error && (
        <div className="text-xs font-medium text-destructive">✗ Error</div>
      )}

      {/* Attributes table */}
      {span.attributes.length > 0 && (
        <div className="border-t border-border pt-1.5">
          <table className="text-xs w-full">
            <tbody>
              {span.attributes.map(attr => {
                const i18nKey = ATTR_I18N_KEYS[attr.key]
                const displayKey = i18nKey ? t(i18nKey) : attr.key
                return (
                  <tr key={attr.key}>
                    <td className="text-muted-foreground pr-2 py-0.5 whitespace-nowrap align-top font-medium">
                      {displayKey}
                    </td>
                    <td className="font-mono break-all py-0.5 align-top line-clamp-2">
                      {formatValue(attr.value)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
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
