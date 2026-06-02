'use client'

import { cn } from '@/lib/utils'
import type { OtlpSpan, OtlpAttributeValue } from '@/lib/api/grafana'
import { spanDurationMs, isErrorSpan, formatDuration } from '@/lib/otlp-utils'
import { useI18n } from '@/lib/providers'

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
  'article.url':                   'admin.stageAttr_url',
  'article.source':                'admin.stageAttr_source',
  'article.topic_id':              'admin.stageAttr_topicId',
  'article.content_chars':         'admin.stageAttr_contentChars',
  'article.outcome':               'admin.stageAttr_outcome',
  'analysis.id':                   'admin.stageAttr_analysisId',
  'analysis.success':              'admin.stageAttr_success',
  'analysis.error_type':           'admin.stageAttr_errorType',
  'llm.model':                     'admin.stageAttr_llmModel',
  'llm.input_tokens':              'admin.stageAttr_inputTokens',
  'llm.output_tokens':             'admin.stageAttr_outputTokens',
  'tags.group_count':              'admin.stageAttr_tagGroups',
  'tags.total_count':              'admin.stageAttr_totalTags',
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
  const s = v.stringValue ?? '—'
  return s.length > 60 ? `${s.slice(0, 57)}…` : s
}

interface StageCardProps {
  span: OtlpSpan
  className?: string
}

export function StageCard({ span, className }: StageCardProps) {
  const { t } = useI18n()
  const durationMs = spanDurationMs(span)
  const error = isErrorSpan(span)
  const stageI18nKey = STAGE_I18N_KEYS[span.name]
  const label = stageI18nKey ? t(stageI18nKey) : (span.name.split('.').pop() ?? span.name)

  return (
    <div className={cn(
      'rounded-lg border bg-card p-3 min-w-[160px] flex-shrink-0 flex flex-col gap-1.5 border-l-3 rounded-l-lg',
      error ? 'border-l-destructive border-destructive' : 'border-l-emerald-500 border-border',
      className,
    )}>
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <span className={cn('font-semibold text-sm truncate', error && 'text-destructive')}>
          {label}
        </span>
        <span className={cn('text-sm font-semibold shrink-0 text-foreground')}>
          {formatDuration(durationMs)}
        </span>
      </div>

      {/* Status badge */}
      <div className={cn('text-xs font-medium', error ? 'text-destructive' : 'text-emerald-600')}>
        {error ? '✗ Error' : '✓ OK'}
      </div>

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
