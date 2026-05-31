'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { HelpCircle, RotateCw } from 'lucide-react'
import { queryTraces, type TempoTrace, type TempoResponse } from '@/lib/grafana-api'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface TracesTableProps {
  title: string
  query?: string  // TraceQL expression
  from?: string   // "now-24h" or unix seconds string
  to?: string
  limit?: number
  height?: number
  refreshInterval?: number
  grafanaUrl?: string  // for external trace links
  className?: string
  tooltip?: string
  externalData?: TempoResponse
  onRefresh?: () => Promise<void>
}

function parseRelativeSeconds(t: string): number {
  if (/^\d+$/.test(t)) return Number(t)
  const now = Math.floor(Date.now() / 1000)
  const match = t.match(/^now-(\d+)([smhd])$/)
  if (!match) return now
  const [, n, unit] = match
  const multipliers: Record<string, number> = { s: 1, m: 60, h: 3600, d: 86400 }
  return now - Number(n) * (multipliers[unit] ?? 1)
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

export function TracesTable({
  title,
  query,
  from = 'now-24h',
  to = 'now',
  limit = 20,
  height = 300,
  refreshInterval = 60,
  grafanaUrl,
  className,
  tooltip,
  externalData,
  onRefresh,
}: TracesTableProps) {
  const [traces, setTraces] = useState<TempoTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try { await onRefresh?.() } finally { setRefreshing(false) }
  }

  const fetch = useCallback(async () => {
    if (externalData !== undefined || onRefresh !== undefined) return
    const start = parseRelativeSeconds(from === 'now' ? String(Math.floor(Date.now() / 1000)) : from)
    const end = parseRelativeSeconds(to === 'now' ? String(Math.floor(Date.now() / 1000)) : to)
    try {
      const res = await queryTraces({ q: query, start, end, limit })
      if ('error' in res && (res as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        return
      }
      setTraces(res.traces ?? [])
      setError(false)
      setNotConfigured(false)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [query, from, to, limit, externalData])

  useEffect(() => {
    if (externalData === undefined) return
    if ('error' in externalData && (externalData as { error: string }).error === 'not_configured') {
      setNotConfigured(true)
      setLoading(false)
      return
    }
    setTraces(externalData.traces ?? [])
    setError(false)
    setNotConfigured(false)
    setLoading(false)
  }, [externalData])

  useEffect(() => { fetch() }, [fetch])

  useEffect(() => {
    if (externalData !== undefined || !refreshInterval || notConfigured) return
    const id = setInterval(fetch, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [fetch, refreshInterval, notConfigured, externalData])

  const traceUrl = (traceId: string) =>
    grafanaUrl
      ? `${grafanaUrl.replace(/\/$/, '')}/explore?schemaVersion=1&panes={"p":{"datasource":"tempo","queries":[{"query":"${traceId}","queryType":"traceqlSearch","refId":"A"}]}}`
      : undefined

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
          {title}
          {tooltip && (
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="h-3 w-3 shrink-0 cursor-help" data-testid="help-icon" />
              </TooltipTrigger>
              <TooltipContent>{tooltip}</TooltipContent>
            </Tooltip>
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
      <div className="rounded-lg border border-border overflow-auto" style={{ height }}>
        {loading ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}
          </div>
        ) : notConfigured ? (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
            Grafana not configured
          </div>
        ) : error ? (
          <div className="w-full h-full flex items-center justify-center text-destructive text-sm">
            Failed to load traces
          </div>
        ) : traces.length === 0 ? (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
            No traces
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="border-b border-border bg-muted/30 sticky top-0">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium text-muted-foreground">Trace ID</th>
                <th className="px-2 py-1.5 text-left font-medium text-muted-foreground">Root Span</th>
                <th className="px-2 py-1.5 text-left font-medium text-muted-foreground">Service</th>
                <th className="px-2 py-1.5 text-right font-medium text-muted-foreground">Duration</th>
              </tr>
            </thead>
            <tbody>
              {traces.map(trace => {
                const url = traceUrl(trace.traceID)
                return (
                  <tr key={trace.traceID} className="border-b border-border last:border-0 hover:bg-muted/30">
                    <td className="px-2 py-1 font-mono text-primary">
                      {url ? (
                        <a href={url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                          {trace.traceID.slice(0, 8)}…
                        </a>
                      ) : (
                        <span>{trace.traceID.slice(0, 8)}…</span>
                      )}
                    </td>
                    <td className="px-2 py-1 truncate max-w-[200px]">{trace.rootTraceName}</td>
                    <td className="px-2 py-1 text-muted-foreground truncate">{trace.rootServiceName}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{formatDuration(trace.durationMs)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
