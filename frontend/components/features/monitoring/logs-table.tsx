'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { RotateCw } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { queryLogs, type LokiStreamResult, type LokiResponse } from '@/lib/grafana-api'

interface LogEntry {
  ts: string      // ISO string
  level: string
  message: string
}

type LevelFilter = 'all' | 'error' | 'warning' | 'info'

interface LogsTableProps {
  title: string
  query: string
  from?: string
  to?: string
  limit?: number
  height?: number
  refreshInterval?: number
  className?: string
  externalData?: LokiResponse
  onRefresh?: () => Promise<void>
}

function parseNsTime(t: string): string {
  // Nanosecond timestamps: append '000000' to milliseconds (avoids BigInt)
  const nowMs = Date.now()
  const nowNs = nowMs.toString() + '000000'
  if (/^now-/.test(t)) {
    const match = t.match(/^now-(\d+)([smhd])$/)
    if (!match) return nowNs
    const [, n, unit] = match
    const multipliers: Record<string, number> = { s: 1000, m: 60000, h: 3600000, d: 86400000 }
    const offsetMs = Number(n) * (multipliers[unit] ?? 1000)
    return (nowMs - offsetMs).toString() + '000000'
  }
  return t
}

function parseLevel(line: string): string {
  try {
    const obj = JSON.parse(line)
    return String(obj.level ?? obj.severity ?? 'info').toLowerCase()
  } catch {
    if (/error/i.test(line)) return 'error'
    if (/warn/i.test(line)) return 'warning'
    return 'info'
  }
}

function parseMessage(line: string): string {
  try {
    const obj = JSON.parse(line)
    return String(obj.event ?? obj.message ?? obj.msg ?? line)
  } catch {
    return line
  }
}

function flattenStreams(streams: LokiStreamResult[]): LogEntry[] {
  const entries: LogEntry[] = []
  for (const stream of streams) {
    for (const [tsNs, line] of stream.values) {
      entries.push({
        ts: new Date(Math.floor(Number(tsNs) / 1_000_000)).toLocaleTimeString(),
        level: parseLevel(line),
        message: parseMessage(line),
      })
    }
  }
  return entries.sort((a, b) => b.ts.localeCompare(a.ts))
}

const LEVEL_COLORS: Record<string, string> = {
  error: 'text-destructive',
  warning: 'text-yellow-500',
  info: 'text-muted-foreground',
}

export function LogsTable({
  title,
  query,
  from = 'now-6h',
  to = 'now',
  limit = 100,
  height = 300,
  refreshInterval = 60,
  className,
  externalData,
  onRefresh,
}: LogsTableProps) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)
  const [filter, setFilter] = useState<LevelFilter>('all')
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try { await onRefresh?.() } finally { setRefreshing(false) }
  }

  const fetch = useCallback(async () => {
    if (externalData !== undefined) return
    const start = parseNsTime(from)
    const end = parseNsTime(to === 'now' ? `now-0s` : to)
    try {
      const res = await queryLogs({ query, start, end, limit })
      if ('error' in res && (res as { error: string }).error === 'not_configured') {
        setNotConfigured(true)
        return
      }
      if (res.status !== 'success' || !res.data) { setError(true); return }
      setEntries(flattenStreams(res.data.result as LokiStreamResult[]))
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
    if (externalData.status !== 'success' || !externalData.data) {
      setError(true)
      setLoading(false)
      return
    }
    setEntries(flattenStreams(externalData.data.result as LokiStreamResult[]))
    setError(false)
    setNotConfigured(false)
    setLoading(false)
  }, [externalData])

  useEffect(() => {
    fetch()
  }, [fetch])

  useEffect(() => {
    if (externalData !== undefined || !refreshInterval || notConfigured) return
    const id = setInterval(fetch, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [fetch, refreshInterval, notConfigured, externalData])

  const visible = filter === 'all' ? entries : entries.filter(e => e.level === filter)

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        <div className="flex items-center gap-2">
          {!loading && !notConfigured && !error && (
            <select
              className="text-xs border border-border rounded px-1 py-0.5 bg-background"
              value={filter}
              onChange={e => setFilter(e.target.value as LevelFilter)}
            >
              <option value="all">All</option>
              <option value="error">Error</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          )}
          {onRefresh && (
            <button onClick={handleRefresh} disabled={refreshing}
              className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
              aria-label="Refresh">
              <RotateCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
            </button>
          )}
        </div>
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
            Failed to load logs
          </div>
        ) : visible.length === 0 ? (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
            No logs
          </div>
        ) : (
          <table className="w-full text-xs">
            <tbody>
              {visible.map((entry, i) => (
                <tr key={i} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-2 py-1 whitespace-nowrap text-muted-foreground w-20">{entry.ts}</td>
                  <td className={cn('px-2 py-1 whitespace-nowrap font-medium w-16', LEVEL_COLORS[entry.level] ?? 'text-foreground')}>
                    {entry.level.toUpperCase()}
                  </td>
                  <td className="px-2 py-1 font-mono truncate max-w-0">{entry.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
