'use client'

import { useEffect, useState, useCallback } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { MetricsChart } from '@/components/features/monitoring/metrics-chart'
import { LogsTable } from '@/components/features/monitoring/logs-table'
import { TracesTable } from '@/components/features/monitoring/traces-table'
import {
  queryMetrics, queryMetricsBatch, queryLogs, queryLogsBatch,
  queryTraces, queryTracesBatch,
  type PrometheusResponse, type LokiResponse, type TempoResponse, type MetricsBatchItem,
} from '@/lib/grafana-api'
import { TooltipProvider } from '@/components/ui/tooltip'

interface MonitoringContentProps {
  grafanaUrl: string
}

const PROM_STATS: { title: string; query: string; unit?: string }[] = [
  // Operations (0–7)
  { title: 'Total Runs (24h)',           query: 'increase(scraper_runs_total[24h])' },
  { title: 'Recent Run Duration (p100)', query: 'max_over_time(scraper_run_duration_seconds_sum[24h])', unit: 's' },
  { title: 'Avg Duration (p50)',          query: 'avg_over_time(scraper_run_duration_seconds_sum[24h])', unit: 's' },
  { title: 'Error Count (24h)',           query: 'increase(scraper_errors_total[24h])' },
  { title: 'New Articles (24h)',          query: 'increase(scraper_articles_new_total[24h])' },
  { title: 'Duplicate Articles (24h)',    query: 'increase(scraper_articles_duplicate_total[24h])' },
  { title: 'Failed Articles (24h)',       query: 'increase(scraper_errors_total[24h])' },
  { title: 'Articles Found (24h)',        query: 'increase(scraper_articles_found_total[24h])' },
  // Traces (8–10)
  { title: 'Traces (24h)',         query: 'increase(scraper_runs_total[24h])' },
  { title: 'Avg Run Duration P95', query: 'histogram_quantile(0.95, scraper_run_duration_seconds_bucket)', unit: 's' },
  { title: 'Error Spans (24h)',    query: 'increase(scraper_errors_total[24h])' },
]

function extractLastValue(res: PrometheusResponse): string | undefined {
  if ('error' in res) return undefined
  if (res.status === 'success' && res.data?.result.length) {
    const vals = res.data.result[0].values
    if (vals.length) return parseFloat(vals[vals.length - 1][1]).toFixed(1).replace(/\.0$/, '')
  }
  return '0'
}

// ── Operations batch hook ──────────────────────────────────────────────────

const OPS_CHART_ITEMS: MetricsBatchItem[] = [
  { query: 'increase(scraper_articles_new_total[1h])',                              step: '3600' },
  { query: 'scraper_run_duration_seconds_sum / scraper_run_duration_seconds_count', step: '3600' },
  { query: 'increase(scraper_articles_new_total[24h])',                             step: '86400' },
  { query: 'increase(scraper_errors_total[24h])',                                   step: '86400' },
]

function useOperationsBatch() {
  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(8).fill(undefined))
  const [chartData, setChartData] = useState<(PrometheusResponse | undefined)[]>(Array(4).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(12).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const fetchAll = useCallback(async () => {
    const now = Math.floor(Date.now() / 1000)
    const items: MetricsBatchItem[] = [
      ...PROM_STATS.slice(0, 8).map(s => ({ query: s.query, start: now - 86400, end: now, step: '86400' })),
      ...OPS_CHART_ITEMS.map(c => ({ ...c, start: now - 86400, end: now })),
    ]
    try {
      const results = await queryMetricsBatch(items)
      if ('error' in results[0] && (results[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(12).fill(false))
        return
      }
      setStatValues(results.slice(0, 8).map(extractLastValue))
      setChartData(results.slice(8) as PrometheusResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(12).fill(false))
    }
  }, [])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    try {
      if (index < 8) {
        const s = PROM_STATS[index]
        const res = await queryMetrics({ query: s.query, start: now - 86400, end: now, step: '86400' })
        setStatValues(prev => prev.map((v, i) => i === index ? extractLastValue(res) : v))
      } else {
        const c = OPS_CHART_ITEMS[index - 8]
        const res = await queryMetrics({ query: c.query, start: now - 86400, end: now, step: c.step })
        setChartData(prev => prev.map((v, i) => i === (index - 8) ? res : v))
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { statValues, chartData, loading, refreshOne }
}

// ── Logs batch hook ────────────────────────────────────────────────────────

const LOGS_METRIC_ITEMS: MetricsBatchItem[] = [
  { query: `sum by (level) (count_over_time({app="scraper"} [1m]))`, step: '60' },
  { query: `count_over_time({app="scraper",level="error"} [1h])`,   step: '3600' },
  { query: `count_over_time({app="scraper",level="warning"} [1h])`, step: '3600' },
]

const LOGS_TABLE_QUERIES = [
  { query: `{app="scraper"} |= "execution"`,        from: 'now-6h' },
  { query: `{app="scraper"} | json | level="error"`, from: 'now-6h' },
  { query: `{app="scraper"} |= "article_analyzed"`,  from: 'now-6h' },
  { query: `{app="scraper"} |= "analysis_failed"`,   from: 'now-6h' },
]

function useLogsBatch() {
  const [metricData, setMetricData] = useState<(PrometheusResponse | undefined)[]>(Array(3).fill(undefined))
  const [logsData, setLogsData] = useState<(LokiResponse | undefined)[]>(Array(4).fill(undefined))
  const [loading, setLoading] = useState<boolean[]>(Array(7).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const fetchAll = useCallback(async () => {
    const now = Math.floor(Date.now() / 1000)
    const nowNs = Date.now().toString() + '000000'
    const sixHAgoNs = (Date.now() - 6 * 3600 * 1000).toString() + '000000'
    const oneHAgoNs = (Date.now() - 3600 * 1000).toString() + '000000'
    try {
      const [metricResults, logsResults] = await Promise.all([
        queryMetricsBatch(LOGS_METRIC_ITEMS.map(c => ({ ...c, start: now - 3600, end: now }))),
        queryLogsBatch(LOGS_TABLE_QUERIES.map(q => ({ query: q.query, start: sixHAgoNs, end: nowNs, limit: 100 }))),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(7).fill(false))
        return
      }
      setMetricData(metricResults as PrometheusResponse[])
      setLogsData(logsResults as LokiResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(7).fill(false))
    }
  }, [])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    const nowNs = Date.now().toString() + '000000'
    const sixHAgoNs = (Date.now() - 6 * 3600 * 1000).toString() + '000000'
    try {
      if (index < 3) {
        const c = LOGS_METRIC_ITEMS[index]
        const res = await queryMetrics({ query: c.query, start: now - 3600, end: now, step: c.step })
        setMetricData(prev => prev.map((v, i) => i === index ? res : v))
      } else {
        const q = LOGS_TABLE_QUERIES[index - 3]
        const res = await queryLogs({ query: q.query, start: sixHAgoNs, end: nowNs, limit: 100 })
        setLogsData(prev => prev.map((v, i) => i === (index - 3) ? res : v))
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { metricData, logsData, loading, refreshOne }
}

// ── Traces batch hook ──────────────────────────────────────────────────────

const TRACES_METRIC_ITEMS: MetricsBatchItem[] = [
  ...PROM_STATS.slice(8, 11).map(s => ({ query: s.query, step: '86400' })),
  { query: 'increase(scraper_runs_total[5m])', step: '300' },
]

function useTracesBatch() {
  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(3).fill(undefined))
  const [chartData, setChartData] = useState<PrometheusResponse | undefined>(undefined)
  const [tracesData, setTracesData] = useState<TempoResponse | undefined>(undefined)
  const [loading, setLoading] = useState<boolean[]>(Array(5).fill(true))
  const [notConfigured, setNotConfigured] = useState(false)

  const fetchAll = useCallback(async () => {
    const now = Math.floor(Date.now() / 1000)
    try {
      const [metricResults, tracesResults] = await Promise.all([
        queryMetricsBatch(TRACES_METRIC_ITEMS.map(c => ({ ...c, start: now - 86400, end: now }))),
        queryTracesBatch([{ q: '{ resource.service.name = "scrape-analyzer" }', start: now - 86400, end: now, limit: 20 }]),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        setLoading(Array(5).fill(false))
        return
      }
      setStatValues(metricResults.slice(0, 3).map(extractLastValue))
      setChartData(metricResults[3] as PrometheusResponse)
      setTracesData(tracesResults[0] as TempoResponse)
    } catch { /* keep previous data */ } finally {
      setLoading(Array(5).fill(false))
    }
  }, [])

  const refreshOne = useCallback(async (index: number): Promise<void> => {
    setLoading(prev => prev.map((v, i) => i === index ? true : v))
    const now = Math.floor(Date.now() / 1000)
    try {
      if (index < 3) {
        const s = PROM_STATS[8 + index]
        const res = await queryMetrics({ query: s.query, start: now - 86400, end: now, step: '86400' })
        setStatValues(prev => prev.map((v, i) => i === index ? extractLastValue(res) : v))
      } else if (index === 3) {
        const res = await queryMetrics({ query: 'increase(scraper_runs_total[5m])', start: now - 86400, end: now, step: '300' })
        setChartData(res)
      } else {
        const res = await queryTraces({ q: '{ resource.service.name = "scrape-analyzer" }', start: now - 86400, end: now, limit: 20 })
        setTracesData(res)
      }
    } catch { /* leave existing data */ } finally {
      setLoading(prev => prev.map((v, i) => i === index ? false : v))
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    if (notConfigured) return
    const id = setInterval(fetchAll, 60_000)
    return () => clearInterval(id)
  }, [fetchAll, notConfigured])

  return { statValues, chartData, tracesData, loading, refreshOne }
}

// ── Tab sub-components (mount lazily via visited Set) ──────────────────────

const OPS_STAT_TOOLTIPS = [
  'totalRunsTooltip',
  'recentRunDurationP100Tooltip',
  'avgDurationP50Tooltip',
  'errorCountTooltip',
  'newArticlesTooltip',
  'duplicateArticlesTooltip',
  'failedArticlesTooltip',
  'articlesFoundTooltip',
] as const

function OperationsTab() {
  const { t } = useI18n()
  const { statValues: sv, chartData: cd, loading, refreshOne } = useOperationsBatch()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3 mt-4">
        {[0, 1, 2, 3].map(i => (
          <StatCard key={i} title={PROM_STATS[i].title} value={sv[i]} unit={PROM_STATS[i].unit}
            loading={loading[i]} onRefresh={() => refreshOne(i)}
            tooltip={t(`admin.${OPS_STAT_TOOLTIPS[i]}`)} />
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        {[4, 5, 6, 7].map(i => (
          <StatCard key={i} title={PROM_STATS[i].title} value={sv[i]}
            loading={loading[i]} onRefresh={() => refreshOne(i)}
            tooltip={t(`admin.${OPS_STAT_TOOLTIPS[i]}`)} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricsChart title="Article Volume Over Time" query="unused" height={240}
          externalData={cd[0]} onRefresh={() => refreshOne(8)}
          tooltip={t('admin.articleVolumeChartTooltip')} />
        <MetricsChart title="Run Duration Over Time" query="unused" height={240}
          externalData={cd[1]} onRefresh={() => refreshOne(9)}
          tooltip={t('admin.runDurationChartTooltip')} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricsChart title="New Articles by Source" query="unused" chartType="bar" height={240}
          externalData={cd[2]} onRefresh={() => refreshOne(10)}
          tooltip={t('admin.articlesBySourceChartTooltip')} />
        <MetricsChart title="Errors by Type" query="unused" chartType="bar" height={240}
          externalData={cd[3]} onRefresh={() => refreshOne(11)}
          tooltip={t('admin.errorsByTypeChartTooltip')} />
      </div>
    </div>
  )
}

function LogsTab() {
  const { t } = useI18n()
  const { metricData: md, logsData: ld, loading, refreshOne } = useLogsBatch()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-6 gap-3 mt-4">
        <MetricsChart title="Log Volume by Level" query="unused" step="60" height={180}
          className="col-span-4" externalData={md[0]} onRefresh={() => refreshOne(0)}
          tooltip={t('admin.logVolumeChartTooltip')} />
        <div className="col-span-1">
          <StatCard title="Error Count (1h)" value={md[1] ? extractLastValue(md[1]) : undefined}
            loading={loading[1]} onRefresh={() => refreshOne(1)}
            tooltip={t('admin.logErrorCount1hTooltip')} />
        </div>
        <div className="col-span-1">
          <StatCard title="Warning Count (1h)" value={md[2] ? extractLastValue(md[2]) : undefined}
            loading={loading[2]} onRefresh={() => refreshOne(2)}
            tooltip={t('admin.logWarningCount1hTooltip')} />
        </div>
      </div>
      <LogsTable title="Execution Timeline" query="unused" height={300}
        externalData={ld[0]} onRefresh={() => refreshOne(3)}
        tooltip={t('admin.executionTimelineTooltip')} />
      <LogsTable title="Error & Failure Logs" query="unused" height={300}
        externalData={ld[1]} onRefresh={() => refreshOne(4)}
        tooltip={t('admin.errorLogsTooltip')} />
      <div className="grid grid-cols-2 gap-3">
        <LogsTable title="Article Success Logs" query="unused" height={240}
          externalData={ld[2]} onRefresh={() => refreshOne(5)}
          tooltip={t('admin.articleSuccessLogsTooltip')} />
        <LogsTable title="Article Failure Logs" query="unused" height={240}
          externalData={ld[3]} onRefresh={() => refreshOne(6)}
          tooltip={t('admin.articleFailureLogsTooltip')} />
      </div>
    </div>
  )
}

const TRACES_STAT_TOOLTIPS = [
  'tracesCountTooltip',
  'avgRunDurationP95Tooltip',
  'errorSpansTooltip',
] as const

function TracesTab({ grafanaUrl }: { grafanaUrl?: string }) {
  const { t } = useI18n()
  const { statValues: sv, chartData: cd, tracesData: td, loading, refreshOne } = useTracesBatch()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 mt-4">
        {[0, 1, 2].map(i => (
          <StatCard key={i} title={PROM_STATS[8 + i].title} value={sv[i]} unit={PROM_STATS[8 + i].unit}
            loading={loading[i]} onRefresh={() => refreshOne(i)}
            tooltip={t(`admin.${TRACES_STAT_TOOLTIPS[i]}`)} />
        ))}
      </div>
      <MetricsChart title="Span Rate by Operation" query="unused" step="300" height={240}
        externalData={cd} onRefresh={() => refreshOne(3)}
        tooltip={t('admin.spanRateChartTooltip')} />
      <TracesTable title="Recent Traces" query="unused" height={400}
        grafanaUrl={grafanaUrl} externalData={td} onRefresh={() => refreshOne(4)}
        tooltip={t('admin.recentTracesTooltip')} />
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function MonitoringContent({ grafanaUrl }: MonitoringContentProps) {
  const { t } = useI18n()
  const [visited, setVisited] = useState<Set<string>>(new Set(['operations']))

  return (
    <TooltipProvider>
    <div className="max-w-7xl space-y-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
      </div>

      <Tabs defaultValue="operations" onValueChange={tab => setVisited(prev => new Set([...prev, tab]))}>
        <TabsList>
          <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
          <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
          <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
        </TabsList>

        <TabsContent value="operations">
          {visited.has('operations') && <OperationsTab />}
        </TabsContent>
        <TabsContent value="logs">
          {visited.has('logs') && <LogsTab />}
        </TabsContent>
        <TabsContent value="traces">
          {visited.has('traces') && <TracesTab grafanaUrl={grafanaUrl} />}
        </TabsContent>
      </Tabs>
    </div>
    </TooltipProvider>
  )
}