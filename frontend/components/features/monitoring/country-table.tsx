'use client'

import { TablePanel } from '@/components/ui/table-panel'
import { cn } from '@/lib/utils'
import { ISO_ALPHA2_TO_NAME } from '@/lib/iso-country-codes'
import { extractCountryTotals } from './country-map'
import type { PrometheusResponse } from '@/lib/api/grafana'

interface CountryTableProps {
  title: string
  tooltip?: string
  height?: number
  data?: PrometheusResponse | null
  loading?: boolean
  /** Highlights this row and, via CountryPanel's shared state, is what CountryMap pans/zooms
   * to — set from either this table's own row click or clicking a shape on the map. */
  selectedCode?: string | null
  onSelectCountry?: (code: string | null) => void
}

/** Ranked table companion to CountryMap — same query result (extractCountryTotals), just a
 * precise sortable list instead of a shaded shape, for when "which country, exact number" is
 * easier to read off than a color. */
export function CountryTable({
  title, tooltip, height = 240, data, loading, selectedCode, onSelectCountry,
}: CountryTableProps) {
  const totals = extractCountryTotals(data)
  const rows = Object.entries(totals)
    .map(([code, count]) => ({ code, name: ISO_ALPHA2_TO_NAME[code] ?? code, count }))
    .sort((a, b) => b.count - a.count)
  const total = rows.reduce((s, r) => s + r.count, 0)

  const columns = [
    { key: 'rank',    label: '#',         className: 'w-8' },
    { key: 'country', label: 'Country' },
    { key: 'count',   label: 'Requests',  className: 'w-20', align: 'right' as const },
    { key: 'share',   label: 'Share',     className: 'w-16', align: 'right' as const },
  ]

  return (
    <TablePanel title={title} tooltip={tooltip} columns={columns} height={height} loading={loading}>
      {rows.length === 0 ? (
        <tr>
          <td colSpan={columns.length} className="text-center py-8 text-muted-foreground text-xs">
            No data
          </td>
        </tr>
      ) : (
        rows.map((r, i) => (
          <tr
            key={r.code}
            onClick={() => onSelectCountry?.(r.code === selectedCode ? null : r.code)}
            className={cn(
              'border-b border-border last:border-0 hover:bg-muted/30',
              onSelectCountry && 'cursor-pointer',
              r.code === selectedCode && 'bg-primary/10 hover:bg-primary/15',
            )}
          >
            <td className="px-2 py-1 text-muted-foreground">{i + 1}</td>
            <td className="px-2 py-1">{r.name}</td>
            <td className="px-2 py-1 text-right font-mono">{r.count.toLocaleString()}</td>
            <td className="px-2 py-1 text-right text-muted-foreground">
              {total > 0 ? `${((r.count / total) * 100).toFixed(1)}%` : '—'}
            </td>
          </tr>
        ))
      )}
    </TablePanel>
  )
}
