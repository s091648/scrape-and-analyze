'use client'

import { useEffect, useState } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { MetricsChart } from '@/components/features/monitoring/metrics-chart'
import { LogsTable } from '@/components/features/monitoring/logs-table'
import { TracesTable } from '@/components/features/monitoring/traces-table'
import { queryMetricsBatch, queryMetrics, type PrometheusResponse, type MetricsBatchItem } from '@/lib/grafana-api'

interface MonitoringContentProps {
  grafanaUrl: string
}

// All Prometheus stat queries — fetched in a single batch call on mount.
// Index is stable: Operations = 0–7, Traces = 8–10.
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
  { title: 'Traces (24h)',          query: 'increase(scraper_runs_total[24h])' },
  { title: 'Avg Run Duration P95',  query: 'histogram_quantile(0.95, scraper_run_duration_seconds_bucket)', unit: 's' },
  { title: 'Error Spans (24h)',     query: 'increase(scraper_errors_total[24h])' },
]

function extractLastValue(res: PrometheusResponse): string | undefined {
  if ('error' in res) return undefined
  if (res.status === 'success' && res.data?.result.length) {
    const vals = res.data.result[0].values
    if (vals.length) return parseFloat(vals[vals.length - 1][1]).toFixed(1).replace(/\.0$/, '')
  }
  return '0'
}

function usePromStatsBatch() {
  const [values, setValues] = useState<(string | undefined)[]>(Array(PROM_STATS.length).fill(undefined))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const now = Math.floor(Date.now() / 1000)
    const items: MetricsBatchItem[] = PROM_STATS.map(s => ({
      query: s.query,
      start: now - 86400,
      end: now,
      step: '86400',
    }))
    queryMetricsBatch(items)
      .then(results => setValues(results.map(extractLastValue)))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return { values, loading }
}

// Loki metric stat — individual call, only mounted when Logs tab is visited.
function LokiStat({ title, query }: { title: string; query: string }) {
  const [value, setValue] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const now = Math.floor(Date.now() / 1000)
    queryMetrics({ query, start: now - 3600, end: now, step: '3600' })
      .then(res => setValue(extractLastValue(res)))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [query])

  return <StatCard title={title} value={value} loading={loading} />
}

export function MonitoringContent({ grafanaUrl }: MonitoringContentProps) {
  const { t } = useI18n()
  const { values: sv, loading: sl } = usePromStatsBatch()
  // Track which tabs have been visited so content is only mounted on first visit.
  const [visited, setVisited] = useState<Set<string>>(new Set(['operations']))

  return (
    <div className="max-w-7xl space-y-6">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
      </div>

      <Tabs
        defaultValue="operations"
        onValueChange={tab => setVisited(prev => new Set([...prev, tab]))}
      >
        <TabsList>
          <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
          <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
          <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
        </TabsList>

        {/* ── Operations ─────────────────────────────────────────────────── */}
        <TabsContent value="operations">
          {visited.has('operations') && (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3 mt-4">
                {[0, 1, 2, 3].map(i => (
                  <StatCard key={i} title={PROM_STATS[i].title} value={sv[i]} unit={PROM_STATS[i].unit} loading={sl} />
                ))}
              </div>
              <div className="grid grid-cols-4 gap-3">
                {[4, 5, 6, 7].map(i => (
                  <StatCard key={i} title={PROM_STATS[i].title} value={sv[i]} loading={sl} />
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <MetricsChart title="Article Volume Over Time" query="increase(scraper_articles_new_total[1h])" step="3600" height={240} />
                <MetricsChart title="Run Duration Over Time" query="scraper_run_duration_seconds_sum / scraper_run_duration_seconds_count" step="3600" height={240} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <MetricsChart title="New Articles by Source" query="increase(scraper_articles_new_total[24h])" chartType="bar" step="86400" height={240} />
                <MetricsChart title="Errors by Type" query="increase(scraper_errors_total[24h])" chartType="bar" step="86400" height={240} />
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── Logs ───────────────────────────────────────────────────────── */}
        <TabsContent value="logs">
          {visited.has('logs') && (
            <div className="space-y-4">
              <div className="grid grid-cols-6 gap-3 mt-4">
                <MetricsChart
                  title="Log Volume by Level"
                  query={`sum by (level) (count_over_time({app="scraper"} [1m]))`}
                  step="60"
                  height={180}
                  className="col-span-4"
                />
                <div className="col-span-1">
                  <LokiStat title="Error Count (1h)" query={`count_over_time({app="scraper",level="error"} [1h])`} />
                </div>
                <div className="col-span-1">
                  <LokiStat title="Warning Count (1h)" query={`count_over_time({app="scraper",level="warning"} [1h])`} />
                </div>
              </div>
              <LogsTable title="Execution Timeline" query={`{app="scraper"} |= "execution"`} from="now-6h" height={300} />
              <LogsTable title="Error & Failure Logs" query={`{app="scraper"} | json | level="error"`} from="now-6h" height={300} />
              <div className="grid grid-cols-2 gap-3">
                <LogsTable title="Article Success Logs" query={`{app="scraper"} |= "article_analyzed"`} from="now-6h" height={240} />
                <LogsTable title="Article Failure Logs" query={`{app="scraper"} |= "analysis_failed"`} from="now-6h" height={240} />
              </div>
            </div>
          )}
        </TabsContent>

        {/* ── Traces ─────────────────────────────────────────────────────── */}
        <TabsContent value="traces">
          {visited.has('traces') && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3 mt-4">
                {[8, 9, 10].map(i => (
                  <StatCard key={i} title={PROM_STATS[i].title} value={sv[i]} unit={PROM_STATS[i].unit} loading={sl} />
                ))}
              </div>
              <MetricsChart
                title="Span Rate by Operation"
                query="increase(scraper_runs_total[5m])"
                step="300"
                height={240}
              />
              <TracesTable
                title="Recent Traces"
                query='{ resource.service.name = "scrape-analyzer" }'
                from="now-24h"
                height={400}
                grafanaUrl={grafanaUrl}
              />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
