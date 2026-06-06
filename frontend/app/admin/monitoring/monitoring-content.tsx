'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { MetricsChart } from '@/components/features/monitoring/metrics-chart'
import { LogsTable } from '@/components/features/monitoring/logs-table'
import { TracesTable } from '@/components/features/monitoring/traces-table'
import {
  queryMetricsBatch, queryLokiMetricsBatch, queryLogsBatch,
  queryTracesBatch,
  type PrometheusResponse, type LokiResponse, type TempoResponse, type MetricsBatchItem,
} from '@/lib/api/grafana'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  LogLevel, LokiLabel,
  lokiStreamSelector, traceQLServiceMatch,
} from '@/lib/observability-constants'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { RotateCw } from 'lucide-react'

// ── Types ──────────────────────────────────────────────────────────────────

type Environment = 'all' | 'local' | 'production' | string
type TimeRange = '6h' | '24h' | '3d' | '7d'

interface MonitoringFilters {
  timeRange: TimeRange
  environment: Environment
}

const TIME_RANGE_SECONDS: Record<TimeRange, number> = {
  '6h':  6 * 3600,
  '24h': 24 * 3600,
  '3d':  3 * 86400,
  '7d':  7 * 86400,
}

const TIME_RANGES: TimeRange[] = ['6h', '24h', '3d', '7d']

/** PromQL/LogQL range vector label covering the full selected duration */
function fullRangeVec(seconds: number): string {
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

const DEFAULT_FILTERS: MonitoringFilters = {
  timeRange: '24h',
  environment: 'all',
}

function applyEnvToLokiQuery(query: string, environment: Environment): string {
  if (environment === 'all') return query
  const envLabel = `${LokiLabel.ENV}="${environment}"`
  return query
    .replace(/\{app="scraper"\}/g, `{app="scraper", ${envLabel}}`)
    .replace(/\{app="scraper", (?!env=)/g, `{app="scraper", ${envLabel}, `)
}

interface MonitoringContentProps {
  grafanaUrl: string
  appEnv: string
}

// ── Panel descriptor types ─────────────────────────────────────────────────

interface StatPanelDef {
  titleKey: string
  buildQuery: (rangeVec: string, env?: string) => string
  step: string
  unit?: string
  tooltipKey: string
  queryType?: 'loki'
}

interface ChartPanelDef {
  titleKey: string
  buildQuery: (rangeVec: string, env?: string) => string
  step: string
  chartType?: 'line' | 'bar'
  height: number
  tooltipKey: string
  queryType?: 'loki'
  seriesColors?: Record<string, string>
}

interface LogTablePanelDef {
  titleKey: string
  query: string
  height: number
  tooltipKey: string
}

interface TracesTablePanelDef {
  titleKey: string
  traceQuery: string
  height: number
  tooltipKey: string
}

// ── Operations panel descriptors ───────────────────────────────────────────

const OPS_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.totalRuns',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [${rv}]))`,                                             step: '3600', tooltipKey: 'admin.totalRunsTooltip' },
  { queryType: 'loki', titleKey: 'admin.newArticles',       buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [${rv}]))`,                                           step: '3600', tooltipKey: 'admin.newArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.duplicateArticles', buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "article_duplicate_skipped" [${rv}]))`,                                    step: '3600', tooltipKey: 'admin.duplicateArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.errorCount',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" [${rv}]))`,                                        step: '3600', tooltipKey: 'admin.errorCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.failedArticles',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "llm_analysis_failed" [${rv}]))`,                                          step: '3600', tooltipKey: 'admin.failedArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.articlesFound',     buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event =~ "analysis_completed|article_duplicate_skipped" [${rv}]))`,               step: '3600', tooltipKey: 'admin.articlesFoundTooltip' },
  { queryType: 'loki', titleKey: 'admin.recentRunDurationP100', buildQuery: rv => `max(max_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`, step: '3600', unit: 's', tooltipKey: 'admin.recentRunDurationP100Tooltip' },
  { queryType: 'loki', titleKey: 'admin.avgDurationP50',        buildQuery: rv => `avg(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`, step: '3600', unit: 's', tooltipKey: 'admin.avgDurationP50Tooltip' },
]

const OPS_CHARTS: ChartPanelDef[] = [
  // Daily step: count_over_time([1d]) + step=86400 so each point = that day's article count
  { queryType: 'loki', titleKey: 'admin.articleVolumeChart',    buildQuery: _rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [1d]))`,                                                                       step: '86400', height: 240, tooltipKey: 'admin.articleVolumeChartTooltip' },
  // avg() collapses per-run series from unwrap into a single time series
  { queryType: 'loki', titleKey: 'admin.runDurationChart',      buildQuery: _rv => `avg(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [1h]))`,                                               step: '3600',  height: 240, tooltipKey: 'admin.runDurationChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.articlesBySourceChart', buildQuery: _rv => `sum by (source) (count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [1d]))`,                                                          step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.articlesBySourceChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.errorsByTypeChart',     buildQuery: _rv => `sum by (event) (count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" | json | event != "" [1d]))`,                                    step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.errorsByTypeChartTooltip' },
]

// ── Logs panel descriptors ─────────────────────────────────────────────────

const LOG_LEVEL_CHART_COLORS: Record<string, string> = {
  error: 'hsl(347,74%,55%)',   // --destructive (dark)
  warn:  'hsl(48,96%,53%)',    // yellow-500
  info:  'hsl(0,0%,55%)',      // --muted-foreground solid equivalent
}

const LOGS_VOLUME_CHART: ChartPanelDef = {
  titleKey: 'admin.logVolumeChart',
  buildQuery: _rv => `sum by (${LokiLabel.DETECTED_LEVEL}) (count_over_time(${lokiStreamSelector()}[1m]))`,
  step: '60',
  height: 180,
  tooltipKey: 'admin.logVolumeChartTooltip',
  seriesColors: LOG_LEVEL_CHART_COLORS,
}

const LOGS_STAT_PANELS: StatPanelDef[] = [
  { titleKey: 'admin.logErrorCount',   buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.ERROR}" [${rv}]))`, step: '3600', tooltipKey: 'admin.logErrorCountTooltip' },
  { titleKey: 'admin.logWarningCount', buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "warn" [${rv}]))`,              step: '3600', tooltipKey: 'admin.logWarningCountTooltip' },
]

// Error → Warning → Info order
const LOGS_TABLE_PANELS: LogTablePanelDef[] = [
  { titleKey: 'admin.errorLogs',   query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.ERROR}"`, height: 300, tooltipKey: 'admin.errorLogsTooltip' },
  { titleKey: 'admin.warningLogs', query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "warn"`,              height: 300, tooltipKey: 'admin.warningLogsTooltip' },
  { titleKey: 'admin.infoLogs',    query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.INFO}"`,  height: 300, tooltipKey: 'admin.infoLogsTooltip' },
]

// ── Traces panel descriptors ───────────────────────────────────────────────

const TRACES_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.tracesCount',       buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [${rv}]))`,                                   step: '3600', tooltipKey: 'admin.tracesCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.avgRunDurationP95', buildQuery: rv => `max(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`,         step: '3600', unit: 's', tooltipKey: 'admin.avgRunDurationP95Tooltip' },
  { queryType: 'loki', titleKey: 'admin.errorSpans',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" [${rv}]))`,                                step: '3600', tooltipKey: 'admin.errorSpansTooltip' },
]

const TRACES_SPAN_CHART: ChartPanelDef = {
  queryType: 'loki',
  titleKey: 'admin.spanRateChart',
  // [1h] + step=3600 (instead of [5m]/300) prevents 576-point range and sparse gaps
  buildQuery: _rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [1h]))`,
  step: '3600',
  height: 240,
  tooltipKey: 'admin.spanRateChartTooltip',
}

const TRACES_TABLE_PANEL: TracesTablePanelDef = {
  titleKey: 'admin.recentTraces',
  traceQuery: traceQLServiceMatch(),
  height: 400,
  tooltipKey: 'admin.recentTracesTooltip',
}

// ── Shared helper ──────────────────────────────────────────────────────────

function extractLastValue(res: PrometheusResponse): string | undefined {
  if ('error' in res) return undefined
  if (res.status === 'success' && res.data?.result.length) {
    const vals = res.data.result[0].values
    if (vals.length) return parseFloat(vals[vals.length - 1][1]).toFixed(1).replace(/\.0$/, '')
  }
  return '0'
}

// ── Operations batch hook ──────────────────────────────────────────────────

function useOperationsBatch(startSec: number, endSec: number, environment: Environment) {
  const env = environment === 'all' ? undefined : environment
  const rangeVec = fullRangeVec(endSec - startSec)

  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(OPS_STATS.length).fill(undefined))
  const [chartData, setChartData] = useState<(PrometheusResponse | undefined)[]>(Array(OPS_CHARTS.length).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(OPS_STATS.length + OPS_CHARTS.length).fill(true))

  const fetchAll = useCallback(async () => {
    setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(true))
    const promItems: MetricsBatchItem[] = [
      ...OPS_STATS.filter(s => s.queryType !== 'loki').map(s => ({ query: s.buildQuery(rangeVec, env), start: startSec, end: endSec, step: s.step })),
      ...OPS_CHARTS.filter(c => c.queryType !== 'loki').map(c => ({ query: c.buildQuery(rangeVec, env), start: startSec, end: endSec, step: c.step })),
    ]
    const lokiItems: MetricsBatchItem[] = [
      ...OPS_STATS.filter(s => s.queryType === 'loki').map(s => ({ query: applyEnvToLokiQuery(s.buildQuery(rangeVec), environment), start: startSec, end: endSec, step: s.step })),
      ...OPS_CHARTS.filter(c => c.queryType === 'loki').map(c => ({ query: applyEnvToLokiQuery(c.buildQuery(rangeVec), environment), start: startSec, end: endSec, step: c.step })),
    ]
    try {
      const [promResults, lokiResults] = await Promise.all([
        promItems.length > 0 ? queryMetricsBatch(promItems) : Promise.resolve([]),
        lokiItems.length > 0 ? queryLokiMetricsBatch(lokiItems) : Promise.resolve([]),
      ])
      if (promItems.length > 0 && 'error' in promResults[0] && (promResults[0] as { error: string }).error === 'not_configured') {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        setChartData(Array(OPS_CHARTS.length).fill(err))
        setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(false))
        return
      }
      const newStatValues: (string | undefined)[] = new Array(OPS_STATS.length).fill(undefined)
      let pi = 0, li = 0
      for (let i = 0; i < OPS_STATS.length; i++) {
        newStatValues[i] = OPS_STATS[i].queryType === 'loki'
          ? extractLastValue(lokiResults[li++] as PrometheusResponse)
          : extractLastValue(promResults[pi++])
      }
      const newChartData: (PrometheusResponse | undefined)[] = []
      for (let i = 0; i < OPS_CHARTS.length; i++) {
        newChartData.push(OPS_CHARTS[i].queryType === 'loki'
          ? lokiResults[li++] as PrometheusResponse
          : promResults[pi++] as PrometheusResponse)
      }
      setStatValues(newStatValues)
      setChartData(newChartData)
    } catch { /* keep previous data */ } finally {
      setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(false))
    }
  }, [startSec, endSec, rangeVec, env, environment])

  useEffect(() => { fetchAll() }, [fetchAll])

  return { statValues, chartData, loading, refresh: fetchAll }
}

// ── Logs batch hook ────────────────────────────────────────────────────────

const LOGS_NUM_METRIC = 1 + LOGS_STAT_PANELS.length

function useLogsBatch(startSec: number, endSec: number, environment: Environment) {
  const env = environment === 'all' ? undefined : environment
  const rangeVec = fullRangeVec(endSec - startSec)

  const [metricData, setMetricData] = useState<(PrometheusResponse | undefined)[]>(Array(LOGS_NUM_METRIC).fill(undefined))
  const [logsData, setLogsData] = useState<(LokiResponse | undefined)[]>(Array(LOGS_TABLE_PANELS.length).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))

  const fetchAll = useCallback(async () => {
    setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))
    const startNs = (startSec * 1000).toString() + '000000'
    const endNs = (endSec * 1000).toString() + '000000'
    const allMetricPanels = [LOGS_VOLUME_CHART, ...LOGS_STAT_PANELS]
    try {
      const [metricResults, logsResults] = await Promise.all([
        queryLokiMetricsBatch(allMetricPanels.map(p => ({
          query: applyEnvToLokiQuery(p.buildQuery(rangeVec, env), environment),
          step: p.step, start: startSec, end: endSec,
        }))),
        queryLogsBatch(LOGS_TABLE_PANELS.map(p => ({
          query: applyEnvToLokiQuery(p.query, environment),
          start: startNs, end: endNs, limit: 500,
        }))),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const logsErr = { error: 'not_configured' } as unknown as LokiResponse
        setMetricData(Array(LOGS_NUM_METRIC).fill(err))
        setLogsData(Array(LOGS_TABLE_PANELS.length).fill(logsErr))
        setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
        return
      }
      setMetricData(metricResults as PrometheusResponse[])
      setLogsData(logsResults as LokiResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
    }
  }, [startSec, endSec, rangeVec, env, environment])

  useEffect(() => { fetchAll() }, [fetchAll])

  return { metricData, logsData, loading, refresh: fetchAll }
}

// ── Traces batch hook ──────────────────────────────────────────────────────

function useTracesBatch(startSec: number, endSec: number, environment: Environment) {
  const rangeVec = fullRangeVec(endSec - startSec)

  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(TRACES_STATS.length).fill(undefined))
  const [chartData, setChartData] = useState<PrometheusResponse | undefined>(undefined)
  const [tracesData, setTracesData] = useState<TempoResponse | undefined>(undefined)
  const [loading, setLoading] = useState<boolean[]>(Array(TRACES_STATS.length + 2).fill(true))

  const traceQuery = environment === 'all' ? TRACES_TABLE_PANEL.traceQuery : traceQLServiceMatch(environment)

  const fetchAll = useCallback(async () => {
    setLoading(Array(TRACES_STATS.length + 2).fill(true))
    try {
      const lokiItems = [
        ...TRACES_STATS.map(s => ({ query: applyEnvToLokiQuery(s.buildQuery(rangeVec), environment), step: s.step, start: startSec, end: endSec })),
        { query: applyEnvToLokiQuery(TRACES_SPAN_CHART.buildQuery(rangeVec), environment), step: TRACES_SPAN_CHART.step, start: startSec, end: endSec },
      ]
      const [lokiResults, tracesResults] = await Promise.all([
        queryLokiMetricsBatch(lokiItems),
        queryTracesBatch([{ q: traceQuery, start: startSec, end: endSec, limit: 20 }]),
      ])
      if ('error' in lokiResults[0] && (lokiResults[0] as { error: string }).error === 'not_configured') {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const tracesErr = { error: 'not_configured' } as unknown as TempoResponse
        setChartData(err)
        setTracesData(tracesErr)
        setLoading(Array(TRACES_STATS.length + 2).fill(false))
        return
      }
      setStatValues(lokiResults.slice(0, TRACES_STATS.length).map(r => extractLastValue(r as PrometheusResponse)))
      setChartData(lokiResults[TRACES_STATS.length] as PrometheusResponse)
      setTracesData(tracesResults[0] as TempoResponse)
    } catch { /* keep previous data */ } finally {
      setLoading(Array(TRACES_STATS.length + 2).fill(false))
    }
  }, [startSec, endSec, rangeVec, environment, traceQuery])

  useEffect(() => { fetchAll() }, [fetchAll])

  return { statValues, chartData, tracesData, loading, refresh: fetchAll }
}

// ── Tab sub-components ─────────────────────────────────────────────────────

function OperationsTab({
  statValues: sv, chartData: cd, loading, timeRangeSeconds, rangeLabel,
}: {
  statValues: (string | undefined)[]
  chartData: (PrometheusResponse | undefined)[]
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const { t } = useI18n()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3 mt-4">
        {OPS_STATS.slice(0, 4).map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {OPS_STATS.slice(4).map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[4 + i]} unit={p.unit}
            loading={loading[4 + i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {OPS_CHARTS.slice(0, 2).map((p, i) => (
          <MetricsChart key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" step={p.step} height={p.height}
            chartType={p.chartType} timeRangeSeconds={timeRangeSeconds}
            externalData={cd[i]} externalLoading={loading[OPS_STATS.length + i]}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {OPS_CHARTS.slice(2).map((p, i) => (
          <MetricsChart key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" step={p.step} height={p.height}
            chartType={p.chartType} timeRangeSeconds={timeRangeSeconds}
            externalData={cd[2 + i]} externalLoading={loading[OPS_STATS.length + 2 + i]}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
    </div>
  )
}

function LogsTab({
  metricData: md, logsData: ld, loading, timeRangeSeconds, rangeLabel,
}: {
  metricData: (PrometheusResponse | undefined)[]
  logsData: (LokiResponse | undefined)[]
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const { t } = useI18n()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-6 gap-3 mt-4">
        <MetricsChart title={t(LOGS_VOLUME_CHART.titleKey, { range: rangeLabel })} query="unused" step={LOGS_VOLUME_CHART.step}
          height={LOGS_VOLUME_CHART.height} className="col-span-4" timeRangeSeconds={timeRangeSeconds}
          externalData={md[0]} externalLoading={loading[0]}
          seriesColors={LOGS_VOLUME_CHART.seriesColors}
          tooltip={t(LOGS_VOLUME_CHART.tooltipKey, { range: rangeLabel })} />
        {LOGS_STAT_PANELS.map((p, i) => (
          <div key={i} className="col-span-1">
            <StatCard title={t(p.titleKey, { range: rangeLabel })} value={md[i + 1] ? extractLastValue(md[i + 1]!) : undefined}
              loading={loading[i + 1]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {LOGS_TABLE_PANELS.map((p, i) => (
          <LogsTable key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" height={p.height}
            externalData={ld[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
    </div>
  )
}

function TracesTab({
  grafanaUrl, statValues: sv, chartData: cd, tracesData: td, loading, timeRangeSeconds, rangeLabel,
}: {
  grafanaUrl?: string
  statValues: (string | undefined)[]
  chartData: PrometheusResponse | undefined
  tracesData: TempoResponse | undefined
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const { t } = useI18n()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 mt-4">
        {TRACES_STATS.map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <MetricsChart title={t(TRACES_SPAN_CHART.titleKey, { range: rangeLabel })} query="unused" step={TRACES_SPAN_CHART.step}
        height={TRACES_SPAN_CHART.height} timeRangeSeconds={timeRangeSeconds}
        externalData={cd} externalLoading={loading[TRACES_STATS.length]}
        tooltip={t(TRACES_SPAN_CHART.tooltipKey, { range: rangeLabel })} />
      <TracesTable title={t(TRACES_TABLE_PANEL.titleKey, { range: rangeLabel })} query="unused" height={TRACES_TABLE_PANEL.height}
        grafanaUrl={grafanaUrl} externalData={td}
        tooltip={t(TRACES_TABLE_PANEL.tooltipKey, { range: rangeLabel })} />
    </div>
  )
}

// ── Filter bar ─────────────────────────────────────────────────────────────

function FilterBar({
  filters, onChange, appEnv,
}: {
  filters: MonitoringFilters
  onChange: (f: MonitoringFilters) => void
  appEnv: string
}) {
  const { t } = useI18n()
  return (
    <div className="flex flex-wrap gap-4 items-center pb-4 border-b border-border">
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">{t('admin.filterTimeRange')}:</span>
        <div className="flex gap-1">
          {TIME_RANGES.map(tr => (
            <button
              key={tr}
              onClick={() => onChange({ ...filters, timeRange: tr })}
              className={cn(
                'text-xs px-2.5 py-1 rounded-lg border transition-colors',
                filters.timeRange === tr
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground',
              )}
            >
              {tr}
            </button>
          ))}
        </div>
      </div>
      {appEnv === 'local' && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">{t('admin.filterEnvironment')}:</span>
          <NativeSelect size="sm" value={filters.environment}
            onChange={e => onChange({ ...filters, environment: e.target.value as Environment })}>
            <option value="all">{t('admin.filterAll')}</option>
            <option value="local">local</option>
            <option value="production">production</option>
            <option value="test">test</option>
          </NativeSelect>
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function MonitoringContent({ grafanaUrl, appEnv }: MonitoringContentProps) {
  const { t } = useI18n()
  const [filters, setFilters] = useState<MonitoringFilters>(DEFAULT_FILTERS)
  // refreshKey increments on manual Refresh so startSec/endSec update to current time
  const [refreshKey, setRefreshKey] = useState(0)

  const timeRangeSeconds = TIME_RANGE_SECONDS[filters.timeRange]
  const rangeLabel = filters.timeRange
  const effectiveEnv: Environment = appEnv === 'local' ? filters.environment : appEnv

  const [startSec, endSec] = useMemo(() => {
    const now = Math.floor(Date.now() / 1000)
    return [now - timeRangeSeconds, now]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRangeSeconds, refreshKey])

  const { statValues: opsSV, chartData: opsCd, loading: opsLoading } = useOperationsBatch(startSec, endSec, effectiveEnv)
  const { metricData: logsMd, logsData: logsLd, loading: logsLoading } = useLogsBatch(startSec, endSec, effectiveEnv)
  const { statValues: tracesSV, chartData: tracesCd, tracesData: tracesTd, loading: tracesLoading } = useTracesBatch(startSec, endSec, effectiveEnv)

  const isLoading = opsLoading.some(Boolean) || logsLoading.some(Boolean) || tracesLoading.some(Boolean)

  // Incrementing refreshKey updates startSec/endSec → hooks re-fetch with current time
  function handleRefresh() { setRefreshKey(k => k + 1) }

  return (
    <TooltipProvider>
      <div className="max-w-7xl space-y-6">
        <div className="border-b border-border pb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading} className="gap-1.5">
            <RotateCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
            {t('admin.refreshPage')}
          </Button>
        </div>

        <FilterBar filters={filters} onChange={setFilters} appEnv={appEnv} />

        <Tabs defaultValue="operations">
          <TabsList>
            <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
            <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
            <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
          </TabsList>

          <TabsContent value="operations">
            <OperationsTab statValues={opsSV} chartData={opsCd} loading={opsLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
          </TabsContent>
          <TabsContent value="logs">
            <LogsTab metricData={logsMd} logsData={logsLd} loading={logsLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
          </TabsContent>
          <TabsContent value="traces">
            <TracesTab grafanaUrl={grafanaUrl} statValues={tracesSV} chartData={tracesCd}
              tracesData={tracesTd} loading={tracesLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  )
}
