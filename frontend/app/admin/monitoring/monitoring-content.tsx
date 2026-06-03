'use client'

import { useEffect, useState, useCallback } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { MetricsChart } from '@/components/features/monitoring/metrics-chart'
import { LogsTable } from '@/components/features/monitoring/logs-table'
import { TracesTable } from '@/components/features/monitoring/traces-table'
import {
  queryMetrics, queryMetricsBatch, queryLokiMetricsBatch, queryLogs, queryLogsBatch,
  queryTraces, queryTracesBatch,
  type PrometheusResponse, type LokiResponse, type TempoResponse, type MetricsBatchItem,
} from '@/lib/api/grafana'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  MetricName, LogField, LogLevel, LokiLabel,
  lokiStreamSelector, traceQLServiceMatch, promqlIncrease, promqlEnvMatcher,
} from '@/lib/observability-constants'
import { cn } from '@/lib/utils'

// ── Filter types ───────────────────────────────────────────────────────────

type TimeRange = '6h' | '24h' | '3d' | '7d'
type Environment = 'all' | 'local' | 'production'
type LogLevelFilter = 'all' | 'error' | 'warning' | 'info'

interface MonitoringFilters {
  timeRange: TimeRange
  environment: Environment
  logLevel: LogLevelFilter
}

const TIME_RANGE_SECONDS: Record<TimeRange, number> = {
  '6h': 21600,
  '24h': 86400,
  '3d': 259200,
  '7d': 604800,
}

/** Human-readable label for PromQL/LogQL range vectors */
const TIME_RANGE_PROMQL: Record<TimeRange, string> = {
  '6h': '6h',
  '24h': '24h',
  '3d': '3d',
  '7d': '7d',
}

const DEFAULT_FILTERS: MonitoringFilters = {
  timeRange: '24h',
  environment: 'all',
  logLevel: 'all',
}

function applyEnvToLokiQuery(query: string, environment: Environment): string {
  if (environment === 'all') return query
  const base = lokiStreamSelector()
  const withEnv = lokiStreamSelector({ [LokiLabel.ENV]: environment })
  return query.replaceAll(base, withEnv)
}

interface MonitoringContentProps {
  grafanaUrl: string
}

// ── Panel descriptor types ─────────────────────────────────────────────────

interface StatPanelDef {
  titleKey: string
  buildQuery: (r: TimeRange, env?: string) => string
  step: string
  unit?: string
  tooltipKey: string
}

interface ChartPanelDef {
  titleKey: string
  buildQuery: (r: TimeRange, env?: string) => string
  step: string
  chartType?: 'line' | 'bar'
  height: number
  tooltipKey: string
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
  { titleKey: 'admin.totalRuns',             buildQuery: (r, env) => promqlIncrease(`${MetricName.RUNS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),      step: '3600', tooltipKey: 'admin.totalRunsTooltip' },
  { titleKey: 'admin.recentRunDurationP100', buildQuery: (r, env) => `max_over_time(${MetricName.RUN_DURATION_SECONDS}_sum${promqlEnvMatcher(env)}[${TIME_RANGE_PROMQL[r]}])`, step: '3600', unit: 's', tooltipKey: 'admin.recentRunDurationP100Tooltip' },
  { titleKey: 'admin.avgDurationP50',        buildQuery: (r, env) => `avg_over_time(${MetricName.RUN_DURATION_SECONDS}_sum${promqlEnvMatcher(env)}[${TIME_RANGE_PROMQL[r]}])`, step: '3600', unit: 's', tooltipKey: 'admin.avgDurationP50Tooltip' },
  { titleKey: 'admin.errorCount',            buildQuery: (r, env) => promqlIncrease(`${MetricName.ERRORS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),       step: '3600', tooltipKey: 'admin.errorCountTooltip' },
  { titleKey: 'admin.newArticles',           buildQuery: (r, env) => promqlIncrease(`${MetricName.ARTICLES_NEW_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]), step: '3600', tooltipKey: 'admin.newArticlesTooltip' },
  { titleKey: 'admin.duplicateArticles',     buildQuery: (r, env) => promqlIncrease(`${MetricName.ARTICLES_DUPLICATE_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]), step: '3600', tooltipKey: 'admin.duplicateArticlesTooltip' },
  { titleKey: 'admin.failedArticles',        buildQuery: (r, env) => promqlIncrease(`${MetricName.ERRORS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),       step: '3600', tooltipKey: 'admin.failedArticlesTooltip' },
  { titleKey: 'admin.articlesFound',         buildQuery: (r, env) => promqlIncrease(`${MetricName.ARTICLES_FOUND_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]), step: '3600', tooltipKey: 'admin.articlesFoundTooltip' },
]

const OPS_CHARTS: ChartPanelDef[] = [
  { titleKey: 'admin.articleVolumeChart',    buildQuery: (_r, env) => promqlIncrease(`${MetricName.ARTICLES_NEW_TOTAL}${promqlEnvMatcher(env)}`, '1h'),       step: '3600',  height: 240, tooltipKey: 'admin.articleVolumeChartTooltip' },
  { titleKey: 'admin.runDurationChart',      buildQuery: (_r, env) => `${MetricName.RUN_DURATION_SECONDS}_sum${promqlEnvMatcher(env)} / ${MetricName.RUN_DURATION_SECONDS}_count${promqlEnvMatcher(env)}`, step: '3600',  height: 240, tooltipKey: 'admin.runDurationChartTooltip' },
  { titleKey: 'admin.articlesBySourceChart', buildQuery: (r, env) => promqlIncrease(`${MetricName.ARTICLES_NEW_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]), step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.articlesBySourceChartTooltip' },
  { titleKey: 'admin.errorsByTypeChart',     buildQuery: (r, env) => promqlIncrease(`${MetricName.ERRORS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),     step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.errorsByTypeChartTooltip' },
]

// ── Logs panel descriptors ─────────────────────────────────────────────────

const LOGS_VOLUME_CHART: ChartPanelDef = {
  titleKey: 'admin.logVolumeChart',
  buildQuery: _r => `sum by (${LokiLabel.DETECTED_LEVEL}) (count_over_time(${lokiStreamSelector()}[1m]))`,
  step: '60',
  height: 180,
  tooltipKey: 'admin.logVolumeChartTooltip',
}

const LOGS_STAT_PANELS: StatPanelDef[] = [
  { titleKey: 'admin.logErrorCount',   buildQuery: r => `sum(count_over_time(${lokiStreamSelector({ [LokiLabel.DETECTED_LEVEL]: LogLevel.ERROR })}[${TIME_RANGE_PROMQL[r]}]))`,   step: '3600', tooltipKey: 'admin.logErrorCountTooltip' },
  { titleKey: 'admin.logWarningCount', buildQuery: r => `sum(count_over_time(${lokiStreamSelector({ [LokiLabel.DETECTED_LEVEL]: LogLevel.WARNING })}[${TIME_RANGE_PROMQL[r]}]))`, step: '3600', tooltipKey: 'admin.logWarningCountTooltip' },
]

const PIPELINE_LIFECYCLE_EVENTS = [
  'execution_started', 'execution_completed', 'execution_failed', 'execution_timeout_reached',
  'sources_due', 'no_sources_due',
  'collection_pipeline_completed',
  'discover_produced_fetch_tasks',
  'executor_fetch_complete', 'executor_phase2_complete',
  'pre_fetch_dedup_filtered', 'post_dedup_filtered',
].join('|')

const LOGS_TABLE_PANELS: LogTablePanelDef[] = [
  { titleKey: 'admin.executionTimeline',  query: `${lokiStreamSelector()} | json | ${LogField.EVENT} =~ "${PIPELINE_LIFECYCLE_EVENTS}"`, height: 400, tooltipKey: 'admin.executionTimelineTooltip' },
  { titleKey: 'admin.errorLogs',          query: `${lokiStreamSelector({ [LokiLabel.DETECTED_LEVEL]: LogLevel.ERROR })}`,                height: 300, tooltipKey: 'admin.errorLogsTooltip' },
  { titleKey: 'admin.articleSuccessLogs', query: `${lokiStreamSelector()} | json | ${LogField.EVENT} =~ "analysis_completed|tag_normalization_completed|auto_translation_completed"`, height: 280, tooltipKey: 'admin.articleSuccessLogsTooltip' },
  { titleKey: 'admin.articleFailureLogs', query: `${lokiStreamSelector()} | json | ${LogField.EVENT} =~ ".*_failed"`,                    height: 280, tooltipKey: 'admin.articleFailureLogsTooltip' },
]

// ── Traces panel descriptors ───────────────────────────────────────────────

const TRACES_STATS: StatPanelDef[] = [
  { titleKey: 'admin.tracesCount',      buildQuery: (r, env) => promqlIncrease(`${MetricName.RUNS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),     step: '3600', tooltipKey: 'admin.tracesCountTooltip' },
  { titleKey: 'admin.avgRunDurationP95', buildQuery: (_r, env) => `histogram_quantile(0.95, ${MetricName.RUN_DURATION_SECONDS}_bucket${promqlEnvMatcher(env)})`, step: '3600', unit: 's', tooltipKey: 'admin.avgRunDurationP95Tooltip' },
  { titleKey: 'admin.errorSpans',       buildQuery: (r, env) => promqlIncrease(`${MetricName.ERRORS_TOTAL}${promqlEnvMatcher(env)}`, TIME_RANGE_PROMQL[r]),     step: '3600', tooltipKey: 'admin.errorSpansTooltip' },
]

const TRACES_SPAN_CHART: ChartPanelDef = {
  titleKey: 'admin.spanRateChart',
  buildQuery: (_r, env) => promqlIncrease(`${MetricName.RUNS_TOTAL}${promqlEnvMatcher(env)}`, '5m'),
  step: '300',
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

function useOperationsBatch(timeRange: TimeRange, timeRangeSeconds: number, environment: Environment) {
  const env = environment === 'all' ? undefined : environment
  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(OPS_STATS.length).fill(undefined))
  const [chartData, setChartData] = useState<(PrometheusResponse | undefined)[]>(Array(OPS_CHARTS.length).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(OPS_STATS.length + OPS_CHARTS.length).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const fetchAll = useCallback(async () => {
    setNotConfigured(false)
    setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(true))
    const now = Math.floor(Date.now() / 1000)
    const items: MetricsBatchItem[] = [
      ...OPS_STATS.map(s => ({ query: s.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: s.step })),
      ...OPS_CHARTS.map(c => ({ query: c.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: c.step })),
    ]
    try {
      const results = await queryMetricsBatch(items)
      if ('error' in results[0] && (results[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(false))
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        setChartData(Array(OPS_CHARTS.length).fill(err))
        return
      }
      setStatValues(results.slice(0, OPS_STATS.length).map(extractLastValue))
      setChartData(results.slice(OPS_STATS.length) as PrometheusResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(OPS_STATS.length + OPS_CHARTS.length).fill(false))
    }
  }, [timeRange, timeRangeSeconds, env])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    try {
      if (index < OPS_STATS.length) {
        const s = OPS_STATS[index]
        const res = await queryMetrics({ query: s.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: s.step })
        setStatValues(prev => prev.map((v, i) => i === index ? extractLastValue(res) : v))
      } else {
        const c = OPS_CHARTS[index - OPS_STATS.length]
        const res = await queryMetrics({ query: c.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: c.step })
        setChartData(prev => prev.map((v, i) => i === (index - OPS_STATS.length) ? res : v))
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [timeRange, timeRangeSeconds, env])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { statValues, chartData, loading, refreshOne }
}

// ── Logs batch hook ────────────────────────────────────────────────────────

const LOGS_NUM_METRIC = 1 + LOGS_STAT_PANELS.length // volume chart + stat cards

function useLogsBatch(timeRange: TimeRange, timeRangeSeconds: number, environment: Environment) {
  const env = environment === 'all' ? undefined : environment
  const [metricData, setMetricData] = useState<(PrometheusResponse | undefined)[]>(Array(LOGS_NUM_METRIC).fill(undefined))
  const [logsData, setLogsData] = useState<(LokiResponse | undefined)[]>(Array(LOGS_TABLE_PANELS.length).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const fetchAll = useCallback(async () => {
    setNotConfigured(false)
    setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))
    const now = Math.floor(Date.now() / 1000)
    const nowNs = Date.now().toString() + '000000'
    const startNs = (Date.now() - timeRangeSeconds * 1000).toString() + '000000'
    const allMetricPanels = [LOGS_VOLUME_CHART, ...LOGS_STAT_PANELS]
    try {
      const [metricResults, logsResults] = await Promise.all([
        // LogQL metric queries must go to Loki, not Prometheus
        queryLokiMetricsBatch(allMetricPanels.map(p => ({
          query: applyEnvToLokiQuery(p.buildQuery(timeRange, env), environment),
          step: p.step, start: now - timeRangeSeconds, end: now,
        }))),
        queryLogsBatch(LOGS_TABLE_PANELS.map(p => ({
          query: applyEnvToLokiQuery(p.query, environment),
          start: startNs, end: nowNs, limit: 500,
        }))),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const logsErr = { error: 'not_configured' } as unknown as LokiResponse
        setMetricData(Array(LOGS_NUM_METRIC).fill(err))
        setLogsData(Array(LOGS_TABLE_PANELS.length).fill(logsErr))
        return
      }
      setMetricData(metricResults as PrometheusResponse[])
      setLogsData(logsResults as LokiResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
    }
  }, [timeRange, timeRangeSeconds, env, environment])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    const nowNs = Date.now().toString() + '000000'
    const startNs = (Date.now() - timeRangeSeconds * 1000).toString() + '000000'
    try {
      if (index === 0) {
        const [res] = await queryLokiMetricsBatch([{ query: applyEnvToLokiQuery(LOGS_VOLUME_CHART.buildQuery(timeRange, env), environment), start: now - timeRangeSeconds, end: now, step: LOGS_VOLUME_CHART.step }])
        setMetricData(prev => prev.map((v, i) => i === 0 ? res : v))
      } else if (index < LOGS_NUM_METRIC) {
        const p = LOGS_STAT_PANELS[index - 1]
        const [res] = await queryLokiMetricsBatch([{ query: applyEnvToLokiQuery(p.buildQuery(timeRange, env), environment), start: now - timeRangeSeconds, end: now, step: p.step }])
        setMetricData(prev => prev.map((v, i) => i === index ? res : v))
      } else {
        const p = LOGS_TABLE_PANELS[index - LOGS_NUM_METRIC]
        const res = await queryLogs({ query: applyEnvToLokiQuery(p.query, environment), start: startNs, end: nowNs, limit: 500 })
        setLogsData(prev => prev.map((v, i) => i === (index - LOGS_NUM_METRIC) ? res : v))
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [timeRange, timeRangeSeconds, env, environment])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { metricData, logsData, loading, refreshOne }
}

// ── Traces batch hook ──────────────────────────────────────────────────────

function useTracesBatch(timeRange: TimeRange, timeRangeSeconds: number, environment: Environment) {
  const env = environment === 'all' ? undefined : environment
  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(TRACES_STATS.length).fill(undefined))
  const [chartData, setChartData] = useState<PrometheusResponse | undefined>(undefined)
  const [tracesData, setTracesData] = useState<TempoResponse | undefined>(undefined)
  const [loading, setLoading] = useState<boolean[]>(Array(TRACES_STATS.length + 2).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const traceQuery = environment === 'all' ? TRACES_TABLE_PANEL.traceQuery : traceQLServiceMatch(environment)

  const fetchAll = useCallback(async () => {
    setNotConfigured(false)
    setLoading(Array(TRACES_STATS.length + 2).fill(true))
    const now = Math.floor(Date.now() / 1000)
    try {
      const [metricResults, tracesResults] = await Promise.all([
        queryMetricsBatch([
          ...TRACES_STATS.map(s => ({ query: s.buildQuery(timeRange, env), step: s.step, start: now - timeRangeSeconds, end: now })),
          { query: TRACES_SPAN_CHART.buildQuery(timeRange, env), step: TRACES_SPAN_CHART.step, start: now - timeRangeSeconds, end: now },
        ]),
        queryTracesBatch([{ q: traceQuery, start: now - timeRangeSeconds, end: now, limit: 20 }]),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(TRACES_STATS.length + 2).fill(false))
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const tracesErr = { error: 'not_configured' } as unknown as TempoResponse
        setChartData(err)
        setTracesData(tracesErr)
        return
      }
      setStatValues(metricResults.slice(0, TRACES_STATS.length).map(extractLastValue))
      setChartData(metricResults[TRACES_STATS.length] as PrometheusResponse)
      setTracesData(tracesResults[0] as TempoResponse)
    } catch { /* keep previous data */ } finally {
      setLoading(Array(TRACES_STATS.length + 2).fill(false))
    }
  }, [timeRange, timeRangeSeconds, env, traceQuery])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    try {
      if (index < TRACES_STATS.length) {
        const s = TRACES_STATS[index]
        const res = await queryMetrics({ query: s.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: s.step })
        setStatValues(prev => prev.map((v, i) => i === index ? extractLastValue(res) : v))
      } else if (index === TRACES_STATS.length) {
        const res = await queryMetrics({ query: TRACES_SPAN_CHART.buildQuery(timeRange, env), start: now - timeRangeSeconds, end: now, step: TRACES_SPAN_CHART.step })
        setChartData(res)
      } else {
        const res = await queryTraces({ q: traceQuery, start: now - timeRangeSeconds, end: now, limit: 20 })
        setTracesData(res)
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [timeRange, timeRangeSeconds, env, traceQuery])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { statValues, chartData, tracesData, loading, refreshOne }
}

// ── Tab sub-components (mount lazily via visited Set) ──────────────────────

function OperationsTab({ timeRange, timeRangeSeconds, environment }: { timeRange: TimeRange; timeRangeSeconds: number; environment: Environment }) {
  const { t } = useI18n()
  const rangeLabel = TIME_RANGE_PROMQL[timeRange]
  const { statValues: sv, chartData: cd, loading, refreshOne } = useOperationsBatch(timeRange, timeRangeSeconds, environment)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3 mt-4">
        {OPS_STATS.slice(0, 4).map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} onRefresh={() => refreshOne(i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {OPS_STATS.slice(4).map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[4 + i]}
            loading={loading[4 + i]} onRefresh={() => refreshOne(4 + i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {OPS_CHARTS.slice(0, 2).map((p, i) => (
          <MetricsChart key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" step={p.step} height={p.height}
            timeRangeSeconds={timeRangeSeconds}
            externalData={cd[i]} externalLoading={loading[OPS_STATS.length + i]}
            onRefresh={() => refreshOne(OPS_STATS.length + i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {OPS_CHARTS.slice(2).map((p, i) => (
          <MetricsChart key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" step={p.step} height={p.height}
            chartType={p.chartType} timeRangeSeconds={timeRangeSeconds}
            externalData={cd[2 + i]} externalLoading={loading[OPS_STATS.length + 2 + i]}
            onRefresh={() => refreshOne(OPS_STATS.length + 2 + i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
    </div>
  )
}

function LogsTab({ timeRange, timeRangeSeconds, environment, logLevel }: { timeRange: TimeRange; timeRangeSeconds: number; environment: Environment; logLevel: LogLevelFilter }) {
  const { t } = useI18n()
  const rangeLabel = TIME_RANGE_PROMQL[timeRange]
  const { metricData: md, logsData: ld, loading, refreshOne } = useLogsBatch(timeRange, timeRangeSeconds, environment)
  const forcedLevel = logLevel !== 'all' ? logLevel : undefined
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-6 gap-3 mt-4">
        <MetricsChart title={t(LOGS_VOLUME_CHART.titleKey, { range: rangeLabel })} query="unused" step={LOGS_VOLUME_CHART.step}
          height={LOGS_VOLUME_CHART.height} className="col-span-4" timeRangeSeconds={timeRangeSeconds}
          externalData={md[0]} externalLoading={loading[0]}
          onRefresh={() => refreshOne(0)}
          tooltip={t(LOGS_VOLUME_CHART.tooltipKey, { range: rangeLabel })} />
        {LOGS_STAT_PANELS.map((p, i) => (
          <div key={i} className="col-span-1">
            <StatCard title={t(p.titleKey, { range: rangeLabel })} value={md[i + 1] ? extractLastValue(md[i + 1]!) : undefined}
              loading={loading[i + 1]} onRefresh={() => refreshOne(i + 1)}
              tooltip={t(p.tooltipKey, { range: rangeLabel })} />
          </div>
        ))}
      </div>
      {LOGS_TABLE_PANELS.slice(0, 2).map((p, i) => (
        <LogsTable key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" height={p.height}
          externalData={ld[i]} onRefresh={() => refreshOne(LOGS_NUM_METRIC + i)}
          tooltip={t(p.tooltipKey, { range: rangeLabel })} forcedLevel={forcedLevel} />
      ))}
      <div className="grid grid-cols-2 gap-3">
        {LOGS_TABLE_PANELS.slice(2).map((p, i) => (
          <LogsTable key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" height={p.height}
            externalData={ld[2 + i]} onRefresh={() => refreshOne(LOGS_NUM_METRIC + 2 + i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} forcedLevel={forcedLevel} />
        ))}
      </div>
    </div>
  )
}

function TracesTab({ grafanaUrl, timeRange, timeRangeSeconds, environment }: { grafanaUrl?: string; timeRange: TimeRange; timeRangeSeconds: number; environment: Environment }) {
  const { t } = useI18n()
  const rangeLabel = TIME_RANGE_PROMQL[timeRange]
  const { statValues: sv, chartData: cd, tracesData: td, loading, refreshOne } = useTracesBatch(timeRange, timeRangeSeconds, environment)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 mt-4">
        {TRACES_STATS.map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} onRefresh={() => refreshOne(i)}
            tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <MetricsChart title={t(TRACES_SPAN_CHART.titleKey, { range: rangeLabel })} query="unused" step={TRACES_SPAN_CHART.step}
        height={TRACES_SPAN_CHART.height} timeRangeSeconds={timeRangeSeconds}
        externalData={cd} externalLoading={loading[TRACES_STATS.length]}
        onRefresh={() => refreshOne(TRACES_STATS.length)}
        tooltip={t(TRACES_SPAN_CHART.tooltipKey, { range: rangeLabel })} />
      <TracesTable title={t(TRACES_TABLE_PANEL.titleKey, { range: rangeLabel })} query="unused" height={TRACES_TABLE_PANEL.height}
        grafanaUrl={grafanaUrl} externalData={td}
        onRefresh={() => refreshOne(TRACES_STATS.length + 1)}
        tooltip={t(TRACES_TABLE_PANEL.tooltipKey, { range: rangeLabel })} />
    </div>
  )
}

// ── Filter bar ─────────────────────────────────────────────────────────────

function FilterBar({ filters, onChange }: { filters: MonitoringFilters; onChange: (f: MonitoringFilters) => void }) {
  const { t } = useI18n()
  function set<K extends keyof MonitoringFilters>(key: K, value: MonitoringFilters[K]) {
    onChange({ ...filters, [key]: value })
  }
  return (
    <div className="flex flex-wrap gap-4 items-center text-xs pb-4 border-b border-border">
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">{t('admin.filterTimeRange')}:</span>
        <div className="flex rounded border border-border overflow-hidden">
          {(['6h', '24h', '3d', '7d'] as const).map(v => (
            <button key={v} onClick={() => set('timeRange', v)}
              className={cn('px-2 py-0.5 transition-colors', filters.timeRange === v ? 'bg-primary text-primary-foreground' : 'hover:bg-muted/50')}>
              {v}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">{t('admin.filterEnvironment')}:</span>
        <select value={filters.environment} onChange={e => set('environment', e.target.value as Environment)}
          className="text-xs border border-border rounded px-1.5 py-0.5 bg-background">
          <option value="all">{t('admin.filterAll')}</option>
          <option value="local">local</option>
          <option value="production">production</option>
        </select>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground">{t('admin.filterLogLevel')}:</span>
        <select value={filters.logLevel} onChange={e => set('logLevel', e.target.value as LogLevelFilter)}
          className="text-xs border border-border rounded px-1.5 py-0.5 bg-background">
          <option value="all">{t('admin.logFilterAll')}</option>
          <option value="error">{t('admin.logFilterError')}</option>
          <option value="warning">{t('admin.logFilterWarning')}</option>
          <option value="info">{t('admin.logFilterInfo')}</option>
        </select>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function MonitoringContent({ grafanaUrl }: MonitoringContentProps) {
  const { t } = useI18n()
  const [visited, setVisited] = useState<Set<string>>(new Set(['operations']))
  const [filters, setFilters] = useState<MonitoringFilters>(DEFAULT_FILTERS)
  const timeRangeSeconds = TIME_RANGE_SECONDS[filters.timeRange]

  return (
    <TooltipProvider>
    <div className="max-w-7xl space-y-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
      </div>

      <FilterBar filters={filters} onChange={setFilters} />

      <Tabs defaultValue="operations" onValueChange={tab => setVisited(prev => new Set([...prev, tab]))}>
        <TabsList>
          <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
          <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
          <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
        </TabsList>

        <TabsContent value="operations">
          {visited.has('operations') && <OperationsTab timeRange={filters.timeRange} timeRangeSeconds={timeRangeSeconds} environment={filters.environment} />}
        </TabsContent>
        <TabsContent value="logs">
          {visited.has('logs') && <LogsTab timeRange={filters.timeRange} timeRangeSeconds={timeRangeSeconds} environment={filters.environment} logLevel={filters.logLevel} />}
        </TabsContent>
        <TabsContent value="traces">
          {visited.has('traces') && <TracesTab grafanaUrl={grafanaUrl} timeRange={filters.timeRange} timeRangeSeconds={timeRangeSeconds} environment={filters.environment} />}
        </TabsContent>
      </Tabs>
    </div>
    </TooltipProvider>
  )
}
