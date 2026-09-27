'use client'

import { useEffect, useRef, useState } from 'react'
import { useI18n } from '@/lib/providers'
import { TablePanel, type ColumnDef } from '@/components/ui/table-panel'
import { queryMetricsBatch, fetchQueryTexts, type PrometheusResponse } from '@/lib/api/grafana'
import { pgSelector, PG_APP_DATABASE_MATCHER } from '@/lib/postgres-metrics'

const TOP_QUERY_LIMIT = 15
const UNUSED_INDEX_LIMIT = 20

interface TopQueryRow {
  queryid: string
  totalSeconds: number
  calls: number
  rows: number
  text?: string
}

interface UnusedIndexRow {
  schemaname: string
  relname: string
  indexrelname: string
  sizeBytes: number
}

/** Each query below is evaluated at a single instant (start = end), so every series holds
 * exactly one point — its value over the whole `[rangeVec]` window ending at `endSec`. */
function lastPoints(res: PrometheusResponse | undefined): { metric: Record<string, string>; value: number }[] {
  if (!res || 'error' in res || res.status !== 'success' || !res.data) return []
  return res.data.result.flatMap(r => {
    const last = r.values[r.values.length - 1]
    return last ? [{ metric: r.metric, value: parseFloat(last[1]) }] : []
  })
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${Math.round(bytes / 1024)} kB`
}

function formatNumber(n: number): string {
  return Math.round(n).toLocaleString()
}

/**
 * The Database app's two table panels: the most expensive statements in the selected
 * window (pg_stat_statements, with SQL text resolved by GET /db/query-texts — the metrics
 * only carry `queryid`) and the indexes no scan touched in that window, largest first.
 *
 * Fetches once per distinct (window, environment, refresh) while the Operations tab is
 * active, same contract as the page's own batch hooks.
 */
export function DatabaseTables({
  startSec, endSec, env, rangeVec, rangeLabel, enabled,
}: {
  startSec: number
  endSec: number
  env?: string
  rangeVec: string
  rangeLabel: string
  enabled: boolean
}) {
  const { t } = useI18n()
  const [topQueries, setTopQueries] = useState<TopQueryRow[]>([])
  const [unusedIndexes, setUnusedIndexes] = useState<UnusedIndexRow[]>([])
  const [textsAvailable, setTextsAvailable] = useState(true)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const fetchedForRef = useRef<string | null>(null)

  useEffect(() => {
    const key = `${startSec}:${endSec}:${env ?? ''}`
    if (!enabled || fetchedForRef.current === key) return
    fetchedForRef.current = key

    const statements = pgSelector(env, PG_APP_DATABASE_MATCHER)
    const indexes = pgSelector(env)
    const indexKey = 'schemaname, relname, indexrelname'
    const at = { start: endSec, end: endSec, step: '60' }

    let cancelled = false
    let done = false
    async function load() {
      setLoading(true)
      setFailed(false)
      try {
        const [time, calls, rows, unused] = await queryMetricsBatch([
          { query: `topk(${TOP_QUERY_LIMIT}, sum by (queryid) (increase(pg_stat_statements_seconds_total${statements}[${rangeVec}])) > 0)`, ...at },
          { query: `sum by (queryid) (increase(pg_stat_statements_calls_total${statements}[${rangeVec}]))`, ...at },
          { query: `sum by (queryid) (increase(pg_stat_statements_rows_total${statements}[${rangeVec}]))`, ...at },
          // Every index's size, minus the ones with at least one scan in the window.
          { query: `topk(${UNUSED_INDEX_LIMIT}, max by (${indexKey}) (pg_stat_user_indexes_size_bytes${indexes}) unless on (${indexKey}) (max by (${indexKey}) (increase(pg_stat_user_indexes_idx_scan${indexes}[${rangeVec}])) > 0))`, ...at },
        ])
        if (cancelled) return
        if ([time, calls, rows, unused].some(r => !r || 'error' in r)) {
          setFailed(true)
          return
        }
        const callsById = new Map(lastPoints(calls).map(p => [p.metric.queryid, p.value]))
        const rowsById = new Map(lastPoints(rows).map(p => [p.metric.queryid, p.value]))
        const top: TopQueryRow[] = lastPoints(time)
          .map(p => ({
            queryid: p.metric.queryid,
            totalSeconds: p.value,
            calls: callsById.get(p.metric.queryid) ?? 0,
            rows: rowsById.get(p.metric.queryid) ?? 0,
          }))
          .sort((a, b) => b.totalSeconds - a.totalSeconds)

        const texts = await fetchQueryTexts(top.map(r => r.queryid))
        if (cancelled) return
        const textById = new Map(texts.items.map(i => [i.queryid, i.query]))
        setTextsAvailable(texts.available)
        setTopQueries(top.map(r => ({ ...r, text: textById.get(r.queryid) })))
        setUnusedIndexes(
          lastPoints(unused)
            .map(p => ({
              schemaname: p.metric.schemaname,
              relname: p.metric.relname,
              indexrelname: p.metric.indexrelname,
              sizeBytes: p.value,
            }))
            .sort((a, b) => b.sizeBytes - a.sizeBytes),
        )
      } catch {
        if (!cancelled) setFailed(true)
      } finally {
        done = true
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
      // A load cancelled mid-flight (tab switch, StrictMode remount) never landed its
      // results — forget the key so the next run refetches instead of spinning forever.
      if (!done && fetchedForRef.current === key) fetchedForRef.current = null
    }
  }, [startSec, endSec, env, rangeVec, enabled])

  const queryColumns: ColumnDef[] = [
    { key: 'query', label: t('admin.dbColQuery') },
    { key: 'calls', label: t('admin.dbColCalls'), align: 'right', className: 'w-20' },
    { key: 'total', label: t('admin.dbColTotalTime'), align: 'right', className: 'w-24' },
    { key: 'mean', label: t('admin.dbColMeanTime'), align: 'right', className: 'w-24' },
    { key: 'rows', label: t('admin.dbColRows'), align: 'right', className: 'w-24' },
  ]
  const indexColumns: ColumnDef[] = [
    { key: 'index', label: t('admin.dbColIndex') },
    { key: 'table', label: t('admin.dbColTable') },
    { key: 'size', label: t('admin.dbColSize'), align: 'right', className: 'w-24' },
  ]
  const errorText = failed ? t('admin.dbTableLoadFailed') : undefined

  return (
    <div className="grid grid-cols-1 gap-3">
      <TablePanel
        title={t('admin.dbTopQueries', { range: rangeLabel })}
        tooltip={t('admin.dbTopQueriesTooltip', { range: rangeLabel })}
        columns={queryColumns}
        height={360}
        loading={loading}
        placeholder={errorText ?? (topQueries.length === 0 ? t('admin.dbNoData') : undefined)}
        placeholderError={failed}
      >
        {topQueries.map(r => (
          <tr key={r.queryid} className="border-b border-border last:border-0 hover:bg-muted/40">
            <td className="px-2 py-1 font-mono text-[11px] max-w-0">
              <div className="truncate" title={r.text ?? r.queryid}>
                {r.text ?? (
                  <span className="text-muted-foreground">
                    {textsAvailable ? t('admin.dbQueryTextMissing', { id: r.queryid }) : t('admin.dbQueryTextUnavailable', { id: r.queryid })}
                  </span>
                )}
              </div>
            </td>
            <td className="px-2 py-1 text-right tabular-nums">{formatNumber(r.calls)}</td>
            <td className="px-2 py-1 text-right tabular-nums">{r.totalSeconds.toFixed(1)} s</td>
            <td className="px-2 py-1 text-right tabular-nums">
              {r.calls > 0 ? `${((r.totalSeconds / r.calls) * 1000).toFixed(1)} ms` : '—'}
            </td>
            <td className="px-2 py-1 text-right tabular-nums">{formatNumber(r.rows)}</td>
          </tr>
        ))}
      </TablePanel>
      <TablePanel
        title={t('admin.dbUnusedIndexes', { range: rangeLabel })}
        tooltip={t('admin.dbUnusedIndexesTooltip', { range: rangeLabel })}
        columns={indexColumns}
        height={300}
        loading={loading}
        placeholder={errorText ?? (unusedIndexes.length === 0 ? t('admin.dbNoUnusedIndexes') : undefined)}
        placeholderError={failed}
      >
        {unusedIndexes.map(r => (
          <tr key={`${r.schemaname}.${r.indexrelname}`} className="border-b border-border last:border-0 hover:bg-muted/40">
            <td className="px-2 py-1 font-mono text-[11px]">{r.indexrelname}</td>
            <td className="px-2 py-1 font-mono text-[11px] text-muted-foreground">{r.schemaname}.{r.relname}</td>
            <td className="px-2 py-1 text-right tabular-nums">{formatBytes(r.sizeBytes)}</td>
          </tr>
        ))}
      </TablePanel>
    </div>
  )
}
