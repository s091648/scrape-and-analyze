'use client'

import { Fragment, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { TablePanel } from '@/components/ui/table-panel'
import { cn } from '@/lib/utils'
import { ISO_ALPHA2_TO_NAME } from '@/lib/iso-country-codes'
import { extractCountryCityTotals, extractCountryRoleTotals } from './country-map'
import type { PrometheusResponse } from '@/lib/api/grafana'

// Fixed per-role colors (rather than cycling through MetricsChart's generic COLORS palette)
// so the same role always reads as the same color down every row of the table.
const ROLE_BAR_COLORS: Record<string, string> = {
  admin: 'bg-amber-500',
  user: 'bg-primary',
  guest: 'bg-muted-foreground/40',
}
const ROLE_ORDER = ['admin', 'user', 'guest']

/** Small stacked bar showing a country's guest/user/admin request-share mix at a glance —
 * hover for the exact per-role breakdown. */
function RoleMixBar({ roles }: { roles: Record<string, number> }) {
  const total = Object.values(roles).reduce((s, v) => s + v, 0)
  if (total <= 0) return <span className="text-muted-foreground">—</span>
  const keys = [...ROLE_ORDER, ...Object.keys(roles).filter(r => !ROLE_ORDER.includes(r))]
    .filter(r => (roles[r] ?? 0) > 0)
  const title = keys
    .map(r => `${r}: ${roles[r].toLocaleString()} (${((roles[r] / total) * 100).toFixed(0)}%)`)
    .join(' · ')
  return (
    <div className="flex h-2.5 w-16 rounded-sm overflow-hidden bg-muted" title={title}>
      {keys.map(r => (
        <div
          key={r}
          className={ROLE_BAR_COLORS[r] ?? 'bg-muted-foreground/60'}
          style={{ width: `${(roles[r] / total) * 100}%` }}
        />
      ))}
    </div>
  )
}

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

interface CountryGroup {
  code: string
  name: string
  count: number
  cities: { city?: string; count: number }[]
  /** user_role -> request count within this country, for RoleMixBar. Country-level only —
   * plan doesn't need a per-city role breakdown. */
  roles: Record<string, number>
}

/** Rolls extractCountryCityTotals' flat (geo_country, geo_city) rows back up into one group per
 * country — matching CountryMap's per-country granularity for the collapsed row — with each
 * country's cities kept alongside it, ranked, for CountryTable's expand-to-reveal breakdown.
 * Also merges in extractCountryRoleTotals' (geo_country, user_role) rows for RoleMixBar — same
 * underlying query result, just grouped a second way. */
function groupByCountry(data?: PrometheusResponse | null): CountryGroup[] {
  const groups = new Map<string, CountryGroup>()
  function getGroup(code: string): CountryGroup {
    let g = groups.get(code)
    if (!g) {
      g = { code, name: ISO_ALPHA2_TO_NAME[code] ?? code, count: 0, cities: [], roles: {} }
      groups.set(code, g)
    }
    return g
  }
  for (const { code, city, count } of extractCountryCityTotals(data)) {
    const g = getGroup(code)
    g.count += count
    g.cities.push({ city, count })
  }
  for (const { code, role, count } of extractCountryRoleTotals(data)) {
    const g = getGroup(code)
    g.roles[role] = (g.roles[role] ?? 0) + count
  }
  for (const g of groups.values()) g.cities.sort((a, b) => b.count - a.count)
  return Array.from(groups.values()).sort((a, b) => b.count - a.count)
}

/** Ranked table companion to CountryMap — same query result as the map, grouped back up to one
 * row per country (extractCountryCityTotals via groupByCountry) so it matches the map's
 * granularity at a glance, with each country's city breakdown collapsed underneath it — click a
 * country row (with a chevron, i.e. it resolved more than a bare country) to expand it. */
export function CountryTable({
  title, tooltip, height = 240, data, loading, selectedCode, onSelectCountry,
}: CountryTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const groups = groupByCountry(data)
  const total = groups.reduce((s, g) => s + g.count, 0)

  const columns = [
    { key: 'rank',    label: '#',         className: 'w-8' },
    { key: 'country', label: 'Country' },
    { key: 'count',   label: 'Requests',  className: 'w-20', align: 'right' as const },
    { key: 'share',   label: 'Share',     className: 'w-16', align: 'right' as const },
    { key: 'roles',   label: 'Role Mix',  className: 'w-20' },
  ]

  function toggleExpanded(code: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  return (
    <TablePanel title={title} tooltip={tooltip} columns={columns} height={height} loading={loading}>
      {groups.length === 0 ? (
        <tr>
          <td colSpan={columns.length} className="text-center py-8 text-muted-foreground text-xs">
            No data
          </td>
        </tr>
      ) : (
        groups.map((g, i) => {
          const isExpanded = expanded.has(g.code)
          // A single entry with no resolved city has nothing to reveal — its own row already is
          // all there is (GeoIP only got as far as the country for that traffic).
          const canExpand = g.cities.length > 1 || (g.cities.length === 1 && !!g.cities[0].city)
          return (
            <Fragment key={g.code}>
              <tr
                onClick={() => {
                  if (canExpand) toggleExpanded(g.code)
                  onSelectCountry?.(g.code === selectedCode ? null : g.code)
                }}
                className={cn(
                  'border-b border-border last:border-0 hover:bg-muted/30',
                  (onSelectCountry || canExpand) && 'cursor-pointer',
                  g.code === selectedCode && 'bg-primary/10 hover:bg-primary/15',
                )}
              >
                <td className="px-2 py-1 text-muted-foreground">{i + 1}</td>
                <td className="px-2 py-1">
                  <span className="inline-flex items-center gap-1">
                    {canExpand ? (
                      isExpanded
                        ? <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
                        : <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                    ) : (
                      <span className="inline-block w-3 shrink-0" />
                    )}
                    {g.name}
                  </span>
                </td>
                <td className="px-2 py-1 text-right font-mono">{g.count.toLocaleString()}</td>
                <td className="px-2 py-1 text-right text-muted-foreground">
                  {total > 0 ? `${((g.count / total) * 100).toFixed(1)}%` : '—'}
                </td>
                <td className="px-2 py-1">
                  <RoleMixBar roles={g.roles} />
                </td>
              </tr>
              {isExpanded && g.cities.map(c => (
                <tr
                  key={`${g.code}::${c.city ?? ''}`}
                  onClick={() => onSelectCountry?.(g.code === selectedCode ? null : g.code)}
                  className={cn(
                    'border-b border-border last:border-0 bg-muted/5 hover:bg-muted/20',
                    onSelectCountry && 'cursor-pointer',
                  )}
                >
                  <td className="px-2 py-1" />
                  <td className="px-2 py-1 pl-6 text-muted-foreground">{c.city ?? '—'}</td>
                  <td className="px-2 py-1 text-right font-mono text-muted-foreground">{c.count.toLocaleString()}</td>
                  <td className="px-2 py-1 text-right text-muted-foreground">
                    {total > 0 ? `${((c.count / total) * 100).toFixed(1)}%` : '—'}
                  </td>
                  {/* No per-city role breakdown — RoleMixBar is country-level only. */}
                  <td className="px-2 py-1" />
                </tr>
              ))}
            </Fragment>
          )
        })
      )}
    </TablePanel>
  )
}
