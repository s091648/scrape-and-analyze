'use client'

import { cn } from '@/lib/utils'
import { ChevronRight, ChevronDown, ScrollText } from 'lucide-react'
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
  'article.rag_ingest':                    'admin.stageLabel_ragIngest',
  'weekly_report.topic':                   'admin.stageLabel_weeklyReportTopic',
  'weekly_report.summarize':               'admin.stageLabel_weeklyReportSummarize',
  'weekly_report.image':                   'admin.stageLabel_weeklyReportImage',
  'weekly_report.translate':                'admin.stageLabel_weeklyReportTranslate',
  'weekly_report.notify':                  'admin.stageLabel_weeklyReportNotify',
}

const ATTR_I18N_KEYS: Record<string, string> = {
  'article.id':                    'admin.stageAttr_articleId',
  'article.title':                 'admin.stageAttr_articleTitle',
  'article.url':                   'admin.stageAttr_url',
  'article.source':                'admin.stageAttr_source',
  'article.original_source':       'admin.stageAttr_originalSource',
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
  'rag_ingest.success':            'admin.stageAttr_ragIngestSuccess',
  'rag_ingest.duration_seconds':   'admin.stageAttr_ragIngestDuration',
  'rag_ingest.error_type':         'admin.stageAttr_ragIngestErrorType',
  'weekly_report.article_count':          'admin.stageAttr_weeklyReportArticleCount',
  'weekly_report.outcome':                'admin.stageAttr_weeklyReportOutcome',
  'weekly_report.summarize.success':      'admin.stageAttr_weeklyReportSummarizeSuccess',
  'weekly_report.summarize.error_type':   'admin.stageAttr_weeklyReportSummarizeErrorType',
  'weekly_report.image.success':          'admin.stageAttr_weeklyReportImageSuccess',
  'weekly_report.image.error_type':       'admin.stageAttr_weeklyReportImageErrorType',
  'notify.channel':                       'admin.stageAttr_notifyChannel',
  'notify.success':                       'admin.stageAttr_notifySuccess',
  'notify.error_type':                    'admin.stageAttr_notifyErrorType',
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
  avg: number
  count: number
  durations: number[]
}

// ── KDE helpers ────────────────────────────────────────────────────────────

function erf(x: number): number {
  const sign = x >= 0 ? 1 : -1
  x = Math.abs(x)
  const t = 1 / (1 + 0.3275911 * x)
  const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
  return sign * (1 - poly * Math.exp(-x * x))
}

function normalCDF(x: number): number {
  return 0.5 * (1 + erf(x / Math.SQRT2))
}

function silvermanBw(data: number[]): number {
  const n = data.length
  const mean = data.reduce((s, v) => s + v, 0) / n
  const std = Math.sqrt(data.reduce((s, v) => s + (v - mean) ** 2, 0) / n)
  return std < 1 ? 1 : Math.max(1.06 * std * Math.pow(n, -0.2), 1)
}

function kdeCDF(x: number, data: number[]): number {
  const n = data.length
  if (n === 0) return 0
  const h = silvermanBw(data)
  return data.reduce((sum, xi) => sum + normalCDF((x - xi) / h), 0) / n
}

function kdePDF(x: number, data: number[], h: number): number {
  const INV_SQRT2PI = 1 / Math.sqrt(2 * Math.PI)
  return data.reduce((s, xi) => {
    const u = (x - xi) / h
    return s + INV_SQRT2PI * Math.exp(-0.5 * u * u)
  }, 0) / (data.length * h)
}

// ── KDE distribution sparkline ─────────────────────────────────────────────

function KdeSparkline({ durationMs, durations }: { durationMs: number; durations: number[] }) {
  const W = 216, H = 48, SAMPLES = 80, PAD = 2
  const n = durations.length
  if (n === 0) return null

  const h = silvermanBw(durations)
  const ext = Math.max(2.5 * h, 1)
  const xMin = Math.max(0, Math.min(...durations) - ext)
  const xMax = Math.max(...durations) + ext
  const xRange = xMax - xMin
  if (xRange === 0) return null

  const xs = Array.from({ length: SAMPLES }, (_, i) => xMin + (i / (SAMPLES - 1)) * xRange)
  const dens = xs.map(x => kdePDF(x, durations, h))
  const maxD = Math.max(...dens)
  if (maxD === 0) return null

  const toX = (v: number) => PAD + ((v - xMin) / xRange) * (W - 2 * PAD)
  const toY = (d: number) => (H - PAD) - (d / maxD) * (H - PAD - 4)

  const pts = xs.map((x, i) => `${toX(x).toFixed(1)},${toY(dens[i]).toFixed(1)}`)
  const linePath = `M${pts.join('L')}`
  const areaPath = `M${toX(xMin).toFixed(1)},${H - PAD}L${pts.join('L')}L${toX(xMax).toFixed(1)},${H - PAD}Z`

  const mx = Math.max(PAD, Math.min(W - PAD, toX(durationMs)))
  const my = toY(kdePDF(durationMs, durations, h))

  return (
    <svg width={W} height={H} className="block overflow-visible mt-1.5">
      <path d={areaPath} fill="hsl(var(--foreground))" fillOpacity={0.08} />
      <path d={linePath} fill="none" stroke="hsl(var(--foreground))"
        strokeWidth={1.5} strokeOpacity={0.35} strokeLinecap="round" />
      <line x1={mx.toFixed(1)} y1="0" x2={mx.toFixed(1)} y2={H - PAD}
        stroke="hsl(var(--primary))" strokeWidth={2} />
      <circle cx={mx.toFixed(1)} cy={my.toFixed(1)} r={3.5}
        fill="hsl(var(--primary))" />
    </svg>
  )
}

interface StageCardProps {
  span: OtlpSpan
  className?: string
  thresholds?: SpanPercentileThresholds
  labelOverride?: string
  collapsed?: boolean
  onToggleCollapse?: () => void
  isHighlighted?: boolean
  onViewLogs?: () => void
}

function durationColor(ms: number, thresholds?: SpanPercentileThresholds): string {
  if (!thresholds || thresholds.durations.length === 0) return 'text-foreground'
  const pct = kdeCDF(ms, thresholds.durations) * 100
  if (pct >= 90) return 'text-red-500'
  if (pct >= 80) return 'text-orange-600'
  if (pct >= 70) return 'text-orange-400'
  return 'text-foreground'
}

export function StageCard({ span, className, thresholds, labelOverride, collapsed, onToggleCollapse, isHighlighted, onViewLogs }: StageCardProps) {
  const { t } = useI18n()
  const durationMs = spanDurationMs(span)
  const error = isErrorSpan(span)
  const stageI18nKey = STAGE_I18N_KEYS[span.name]
  const label = labelOverride ?? (stageI18nKey ? t(stageI18nKey) : (span.name.split('.').pop() ?? span.name))

  const startMs = Number(BigInt(span.startTimeUnixNano) / 1_000_000n)
  const startTimeStr = new Date(startMs).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  const hasSufficientData = thresholds && thresholds.count >= 5
  const pct = hasSufficientData ? Math.round(kdeCDF(durationMs, thresholds!.durations) * 100) : undefined

  const durationBadge = hasSufficientData ? (
    <RadixTooltip>
      <TooltipTrigger asChild>
        <span className={cn('text-sm font-semibold shrink-0 cursor-default', durationColor(durationMs, thresholds))}>
          {formatDuration(durationMs)}
        </span>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="bg-popover text-popover-foreground border border-border shadow-md p-3 w-60 max-w-none"
      >
        <p className="text-xs font-medium">
          percentile: {pct}%
          <span className="text-muted-foreground font-normal"> (average: {formatDuration(thresholds!.avg)})</span>
        </p>
        <KdeSparkline durationMs={durationMs} durations={thresholds!.durations} />
        <p className="text-[10px] text-muted-foreground mt-1.5">n={thresholds!.count} · past 7d</p>
      </TooltipContent>
    </RadixTooltip>
  ) : (
    <span className={cn('text-sm font-semibold shrink-0', durationColor(durationMs, thresholds))}>
      {formatDuration(durationMs)}
    </span>
  )

  return (
    <div className={cn(
      'relative rounded-lg border-2 bg-card p-3 min-w-[160px] flex-shrink-0 flex flex-col gap-1.5',
      error ? 'border-destructive' : isHighlighted ? 'border-primary' : 'border-emerald-500',
      className,
    )}>
      {/* Pulsing glow overlay — uses a custom keyframe so the glow pulses independently
          of any Tailwind bundle-inclusion issue with the 'pulse' keyframe */}
      {isHighlighted && (
        <>
          <style>{`
            @keyframes span-glow {
              0%, 100% { opacity: 0.15; }
              50%       { opacity: 1;    }
            }
          `}</style>
          <div
            className="absolute -inset-[3px] rounded-[11px] pointer-events-none"
            style={{
              boxShadow: '0 0 0 2px hsl(var(--primary) / 0.6), 0 0 28px 8px hsl(var(--primary) / 0.45)',
              animation: 'span-glow 1.2s ease-in-out 3',
            }}
          />
        </>
      )}
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
        <div className="flex items-center gap-1.5 shrink-0">
          {onViewLogs && (
            <button
              onClick={e => { e.stopPropagation(); onViewLogs() }}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title="View logs for this span"
            >
              <ScrollText className="h-3.5 w-3.5" />
            </button>
          )}
          {durationBadge}
        </div>
      </div>

      {/* Start time */}
      <p className="text-[10px] text-muted-foreground font-mono leading-tight -mt-0.5">
        {startTimeStr}
      </p>

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
