'use client'

import { useEffect, useState, useCallback } from 'react'
import { queryTraces, type TempoTrace, type TempoResponse } from '@/lib/grafana-api'
import { TablePanel } from '@/components/ui/table-panel'
import { useI18n } from '@/lib/providers'

interface TracesTableProps {
  title: string
  query?: string
  from?: string
  to?: string
  limit?: number
  height?: number
  refreshInterval?: number
  grafanaUrl?: string
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
  if (ms < 1000) return `${ms} ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60000).toFixed(1)} m`
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
  const { t } = useI18n()
  const [traces, setTraces] = useState<TempoTrace[]>([])
  const [loading, setLoading] = useState(true)
  const [notConfigured, setNotConfigured] = useState(false)
  const [error, setError] = useState(false)

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

  const placeholder = notConfigured
    ? t('admin.grafanaNotConfigured')
    : error
    ? t('admin.failedToLoadTraces')
    : undefined

  const columns = [
    { key: 'traceId',   label: t('admin.traceColumnTraceId') },
    { key: 'rootSpan',  label: t('admin.traceColumnRootSpan') },
    { key: 'service',   label: t('admin.traceColumnService') },
    { key: 'duration',  label: t('admin.traceColumnDuration'), align: 'right' as const },
  ]

  return (
    <TablePanel
      title={title}
      tooltip={tooltip}
      onRefresh={onRefresh}
      columns={columns}
      height={height}
      className={className}
      loading={loading}
      placeholder={placeholder}
      placeholderError={error}
    >
      {traces.length === 0 ? (
        <tr>
          <td colSpan={4} className="text-center py-8 text-muted-foreground text-xs">
            {t('admin.noTraces')}
          </td>
        </tr>
      ) : (
        traces.map(trace => {
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
        })
      )}
    </TablePanel>
  )
}
