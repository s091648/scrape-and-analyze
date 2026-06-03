'use client'

import { useEffect, useState, useCallback } from 'react'
import { HelpCircle, RotateCw } from 'lucide-react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import {
  Tooltip as RadixTooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { queryMetrics, type PrometheusResponse, type PrometheusMatrixResult } from '@/lib/api/grafana'

interface DataPoint {
  time: string
  [series: string]: string | number | null
}

interface MetricsChartProps {
  title: string
  query: string
  from?: string
  to?: string
  step?: string
  height?: number
  chartType?: 'line' | 'bar'
  refreshInterval?: number
  className?: string
  tooltip?: string
  timeRangeSeconds?: number
  externalData?: PrometheusResponse
  externalLoading?: boolean
  onRefresh?: () => Promise<void>
}

function parseRelativeTime(t: string): number {
  if (/^\d+$/.test(t)) return Number(t)
  const now = Math.floor(Date.now() / 1000)
  const match = t.match(/^now-(\d+)([smhd])$/)
  if (!match) return now
  const [, n, unit] = match
  const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 }
  return now - Number(n) * (multipliers[unit] ?? 1)
}

function transformMatrix(
  results: PrometheusMatrixResult[],
  step?: string,
  startTs?: number,
  endTs?: number,
): DataPoint[] {
  if (!results.length) return []
  const stepNum = step ? parseInt(step) : 0

  const labelOf = (metric: Record<string, string>) =>
    Object.entries(metric)
      .filter(([k]) => k !== '__name__')
      .map(([, v]) => v)
      .join(', ') || '(other)'

  const allLabels = new Set<string>()
  for (const series of results) allLabels.add(labelOf(series.metric))

  const byTime: Record<number, Record<string, number | null>> = {}

  // Pre-populate null entries for every expected step so gaps are visible
  if (startTs !== undefined && endTs !== undefined && stepNum > 0) {
    const firstTs = Math.ceil(startTs / stepNum) * stepNum
    for (let ts = firstTs; ts <= endTs; ts += stepNum) {
      byTime[ts] = {}
      for (const l of allLabels) byTime[ts][l] = null
    }
  }

  for (const series of results) {
    const label = labelOf(series.metric)
    for (const [ts, val] of series.values) {
      const tsNum = Number(ts)
      if (!byTime[tsNum]) {
        byTime[tsNum] = {}
        for (const l of allLabels) byTime[tsNum][l] = null
      }
      byTime[tsNum][label] = parseFloat(val)
    }
  }

  const rangeSeconds = endTs !== undefined && startTs !== undefined ? endTs - startTs : 0

  return Object.entries(byTime)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([ts, vals]) => {
      const date = new Date(Number(ts) * 1000)
      let time: string
      if (stepNum >= 86400) {
        time = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
      } else if (rangeSeconds > 86400) {
        // Multi-day range: show date + HH:MM so ticks are unambiguous
        time = date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
          + ' ' + date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
      } else {
        time = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
      }
      return { time, ...vals }
    })
}

function processResponse(
  res: PrometheusResponse,
  step?: string,
  startTs?: number,
  endTs?: number,
): { data: DataPoint[]; keys: string[]; notConfigured: boolean; error: boolean } {
  if ('error' in res && (res as { error: string }).error === 'not_configured') {
    return { data: [], keys: [], notConfigured: true, error: false }
  }
  if (res.status !== 'success' || !res.data) {
    return { data: [], keys: [], notConfigured: false, error: true }
  }
  const points = transformMatrix(res.data.result, step, startTs, endTs)
  const keys = points.length ? Object.keys(points[0]).filter(k => k !== 'time') : []
  return { data: points, keys, notConfigured: false, error: false }
}

const COLORS = ['hsl(var(--primary))', 'hsl(217,91%,60%)', 'hsl(142,71%,45%)', 'hsl(38,92%,50%)']

function renderChartTooltip(props: Parameters<typeof ChartTooltip>[0]) {
  return <ChartTooltip {...props} />
}

const fmtNum = (v: number) =>
  Number.isInteger(v) ? v.toString() : parseFloat(v.toFixed(3)).toString()

function ChartTooltip({
  active, payload, label,
}: {
  active?: boolean
  payload?: Array<{ dataKey: string; value: number | null | undefined; color: string; name: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  const valid = payload.filter(p => p.value !== null && p.value !== undefined)
  // No data at this position — let cursor line show but render no box
  if (!valid.length) return null
  return (
    // translateY(-100%) moves the box above the Recharts wrapper anchor,
    // so the tooltip appears over the cursor instead of below it.
    <div
      style={{ transform: 'translateY(calc(-100% - 8px))', pointerEvents: 'none' }}
      className="rounded border border-border bg-background/95 backdrop-blur-sm px-2.5 py-1.5 shadow-sm text-xs"
    >
      <p className="text-muted-foreground mb-0.5">{label}</p>
      {valid.map(p => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {valid.length > 1 && <span className="text-muted-foreground">{p.name}: </span>}
          {fmtNum(p.value as number)}
        </p>
      ))}
    </div>
  )
}

export function MetricsChart({
  title, query, from = 'now-24h', to = 'now', step = '300',
  height = 200, chartType = 'line', refreshInterval = 60,
  className, tooltip, timeRangeSeconds, externalData, externalLoading, onRefresh,
}: MetricsChartProps) {
  const [data, setData] = useState<DataPoint[]>([])
  const [seriesKeys, setSeriesKeys] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  // Controlled mode: process externalData when it arrives/changes
  useEffect(() => {
    if (externalData === undefined) return
    const now = Math.floor(Date.now() / 1000)
    const startTs = timeRangeSeconds ? now - timeRangeSeconds : undefined
    const result = processResponse(externalData, step, startTs, startTs !== undefined ? now : undefined)
    setData(result.data)
    setSeriesKeys(result.keys)
    setNotConfigured(result.notConfigured)
    setError(result.error)
    setLoading(false)
  }, [externalData, step, timeRangeSeconds])

  // Self-fetch mode: only when externalData is not provided
  const doFetch = useCallback(async () => {
    if (externalData !== undefined || onRefresh !== undefined) return
    const startTs = parseRelativeTime(from === 'now' ? String(Math.floor(Date.now() / 1000)) : from)
    const endTs = parseRelativeTime(to === 'now' ? String(Math.floor(Date.now() / 1000)) : to)
    try {
      const res = await queryMetrics({ query, start: startTs, end: endTs, step })
      const result = processResponse(res, step, startTs, endTs)
      setData(result.data)
      setSeriesKeys(result.keys)
      setNotConfigured(result.notConfigured)
      setError(result.error)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [query, from, to, step, externalData])

  useEffect(() => {
    doFetch()
  }, [doFetch])

  useEffect(() => {
    if (externalData !== undefined || !refreshInterval || notConfigured) return
    const id = setInterval(doFetch, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [doFetch, refreshInterval, notConfigured, externalData])

  async function handleRefresh() {
    setRefreshing(true)
    try { await onRefresh?.() } finally { setRefreshing(false) }
  }

  // Show ~6 ticks regardless of total data points; fall back to Recharts default when unknown
  const stepNum = parseInt(step)
  const xAxisInterval: number | 'preserveStartEnd' = (() => {
    if (!timeRangeSeconds || !stepNum || isNaN(stepNum)) return 'preserveStartEnd'
    const totalPoints = Math.ceil(timeRangeSeconds / stepNum)
    if (totalPoints <= 6) return 0
    return Math.round(totalPoints / 6) - 1
  })()

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
          {title}
          {tooltip && (
            <RadixTooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="h-3 w-3 shrink-0 cursor-help" data-testid="help-icon" />
              </TooltipTrigger>
              <TooltipContent>{tooltip}</TooltipContent>
            </RadixTooltip>
          )}
        </p>
        {onRefresh && (
          <button onClick={handleRefresh} disabled={refreshing}
            className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            aria-label="Refresh">
            <RotateCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
          </button>
        )}
      </div>
      <div style={{ height }}>
        {(loading || externalLoading) ? (
          <Skeleton className="w-full h-full rounded-lg" />
        ) : notConfigured ? (
          <div className="w-full h-full flex items-center justify-center border border-dashed border-muted-foreground/40 rounded-lg text-muted-foreground text-sm">
            Grafana not configured
          </div>
        ) : error ? (
          <div className="w-full h-full flex items-center justify-center border border-dashed border-destructive/40 rounded-lg text-destructive text-sm">
            Failed to load data
          </div>
        ) : data.length === 0 ? (
          <div className="w-full h-full flex items-center justify-center border border-dashed border-muted-foreground/40 rounded-lg text-muted-foreground text-sm">
            No data
          </div>
        ) : chartType === 'bar' ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} interval={xAxisInterval} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                content={renderChartTooltip}
                isAnimationActive={false}
                cursor={{ fill: 'hsl(var(--border))', opacity: 0.15 }}
              />
              {seriesKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 10 }} />}
              {seriesKeys.map((k, i) => <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} />)}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} interval={xAxisInterval} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip
                content={renderChartTooltip}
                isAnimationActive={false}
                cursor={{ stroke: 'hsl(var(--border))', strokeWidth: 1, strokeDasharray: '4 2' }}
              />
              {seriesKeys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]}
                  dot={data.length <= 20 ? { r: 3, strokeWidth: 0, fill: COLORS[i % COLORS.length] } : false}
                  strokeWidth={2} connectNulls={true} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
