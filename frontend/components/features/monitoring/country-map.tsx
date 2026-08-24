'use client'

import { useEffect, useMemo, useState } from 'react'
import { ComposableMap, Geographies, Geography, ZoomableGroup } from 'react-simple-maps'
import { geoCentroid } from 'd3-geo'
import { feature } from 'topojson-client'
import type { FeatureCollection, Geometry } from 'geojson'
import { HelpCircle, Plus, Minus } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip as RadixTooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ISO_ALPHA2_TO_NUMERIC, ISO_NUMERIC_TO_ALPHA2 } from '@/lib/iso-country-codes'
import type { PrometheusResponse } from '@/lib/api/grafana'

const MIN_ZOOM = 1
const MAX_ZOOM = 8
/** Zoom level a "navigate to this country" jump settles at — close enough to make a single
 * country legible without being so tight small/island countries clip out of view. */
const FOCUS_ZOOM = 4

/** Natural Earth 110m world topology (via world-atlas, MIT-licensed, no API key) bundled
 * locally instead of hotlinked from a CDN — see frontend/public/data/. */
const GEO_URL = '/data/world-countries-110m.json'

/** Sums every point in each `geo_country` series across the whole selected time range —
 * the map wants one static total per country, not the per-bucket time series MetricsChart's
 * bar/line charts render. Exported so CountryTable (rendered alongside this map from the same
 * query result) uses the identical aggregation instead of duplicating it. */
export function extractCountryTotals(res: PrometheusResponse | null | undefined): Record<string, number> {
  const totals: Record<string, number> = {}
  if (!res || 'error' in res || res.status !== 'success' || !res.data) return totals
  for (const series of res.data.result) {
    const code = series.metric.geo_country
    if (!code) continue
    const sum = series.values.reduce((s, [, v]) => s + parseFloat(v), 0)
    totals[code] = (totals[code] ?? 0) + sum
  }
  return totals
}

interface CountryMapProps {
  title: string
  tooltip?: string
  height?: number
  className?: string
  data?: PrometheusResponse | null
  loading?: boolean
  /** Alpha-2 code to pan/zoom to and outline — set from CountryTable's row click (or from
   * clicking a shape on this map itself, via onSelectCountry). */
  selectedCode?: string | null
  onSelectCountry?: (code: string | null) => void
}

export function CountryMap({
  title, tooltip, height = 320, className, data, loading, selectedCode, onSelectCountry,
}: CountryMapProps) {
  const [hovered, setHovered] = useState<{ name: string; count: number; x: number; y: number } | null>(null)
  const [zoom, setZoom] = useState(1)
  const [center, setCenter] = useState<[number, number]>([0, 0])
  // Fetched once here (rather than left to Geographies' own internal fetch of the `geography`
  // URL) so the same parsed features can also feed geoCentroid() below — Geographies' render
  // prop only exposes geometries deep inside its own render pass, too late to compute a
  // "navigate to this country" target from.
  const [features, setFeatures] = useState<FeatureCollection<Geometry> | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(GEO_URL).then(r => r.json()).then(topology => {
      if (cancelled) return
      const fc = feature(topology, topology.objects.countries) as unknown as FeatureCollection<Geometry>
      setFeatures(fc)
    })
    return () => { cancelled = true }
  }, [])

  const centroidByNumericId = useMemo(() => {
    const map: Record<string, [number, number]> = {}
    if (!features) return map
    for (const f of features.features) {
      if (f.id != null) map[String(f.id)] = geoCentroid(f)
    }
    return map
  }, [features])

  function clampZoom(z: number) {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))
  }

  // "Navigate to" — recenters and zooms in on selectedCode's centroid whenever it changes
  // (from either CountryTable's row click or clicking a shape here — both funnel through the
  // same selectedCode prop, owned by the CountryPanel parent).
  useEffect(() => {
    if (!selectedCode) return
    const numericId = ISO_ALPHA2_TO_NUMERIC[selectedCode]
    const centroid = numericId ? centroidByNumericId[numericId] : undefined
    if (!centroid) return
    setCenter(centroid)
    setZoom(z => Math.max(z, FOCUS_ZOOM))
  }, [selectedCode, centroidByNumericId])

  const totals = extractCountryTotals(data)
  const numericTotals: Record<string, number> = {}
  for (const [alpha2, count] of Object.entries(totals)) {
    const numeric = ISO_ALPHA2_TO_NUMERIC[alpha2]
    if (numeric) numericTotals[numeric] = (numericTotals[numeric] ?? 0) + count
  }
  const max = Math.max(1, ...Object.values(numericTotals))
  const selectedNumericId = selectedCode ? ISO_ALPHA2_TO_NUMERIC[selectedCode] : undefined

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center gap-1 mb-2">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        {tooltip && (
          <RadixTooltip>
            <TooltipTrigger asChild>
              <HelpCircle className="h-3 w-3 shrink-0 cursor-help text-muted-foreground" />
            </TooltipTrigger>
            <TooltipContent>{tooltip}</TooltipContent>
          </RadixTooltip>
        )}
      </div>
      <div className="rounded-lg border border-border overflow-hidden relative bg-muted/10" style={{ height }}>
        {loading || !features ? (
          <div className="p-3 h-full"><Skeleton className="h-full w-full" /></div>
        ) : (
          <ComposableMap projection="geoEqualEarth" style={{ width: '100%', height: '100%' }}>
            {/* ZoomableGroup wires up d3-zoom internally — mouse wheel / pinch zoom and drag-to-pan
                work out of the box; the +/- buttons below just drive the same `zoom` state. */}
            <ZoomableGroup center={center} zoom={zoom} minZoom={MIN_ZOOM} maxZoom={MAX_ZOOM}
              onMoveEnd={({ coordinates, zoom: z }) => { setCenter(coordinates); setZoom(z) }}>
              <Geographies geography={features}>
                {({ geographies }) =>
                  geographies.map(geo => {
                    const id = String(geo.id)
                    const count = numericTotals[id] ?? 0
                    const isSelected = id === selectedNumericId
                    // hsl(var(--primary) / alpha) — mirrors StageCard's KdeSparkline color idiom
                    // (frontend/components/features/monitoring/stage-card.tsx) so this stays
                    // theme-aware (light/dark) without hardcoding a hex palette.
                    const alpha = count > 0 ? 0.18 + 0.72 * (count / max) : 0
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        onMouseEnter={evt => setHovered({ name: String(geo.properties.name), count, x: evt.clientX, y: evt.clientY })}
                        onMouseMove={evt => setHovered(h => h ? { ...h, x: evt.clientX, y: evt.clientY } : h)}
                        onMouseLeave={() => setHovered(null)}
                        onClick={() => onSelectCountry?.(ISO_NUMERIC_TO_ALPHA2[id] ?? null)}
                        style={{
                          default: {
                            fill: count > 0 ? `hsl(var(--primary) / ${alpha})` : 'var(--muted)',
                            stroke: isSelected ? 'var(--primary)' : 'var(--border)',
                            strokeWidth: isSelected ? 1.5 : 0.4,
                            outline: 'none', cursor: onSelectCountry ? 'pointer' : 'default',
                          },
                          hover: {
                            fill: count > 0 ? `hsl(var(--primary) / ${Math.min(1, alpha + 0.25)})` : 'var(--muted)',
                            stroke: isSelected ? 'var(--primary)' : 'var(--border)',
                            strokeWidth: isSelected ? 1.5 : 0.4,
                            outline: 'none', cursor: onSelectCountry ? 'pointer' : 'default',
                          },
                          pressed: { outline: 'none' },
                        }}
                      />
                    )
                  })
                }
              </Geographies>
            </ZoomableGroup>
          </ComposableMap>
        )}
        {!loading && (
          <div className="absolute bottom-2 right-2 flex flex-col rounded border border-border bg-background/90 backdrop-blur-sm overflow-hidden shadow-sm">
            <RadixTooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setZoom(z => clampZoom(z + 1))}
                  disabled={zoom >= MAX_ZOOM}
                  className="h-6 w-6 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer border-b border-border"
                  aria-label="Zoom in"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left">Zoom in (or scroll)</TooltipContent>
            </RadixTooltip>
            <RadixTooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setZoom(z => clampZoom(z - 1))}
                  disabled={zoom <= MIN_ZOOM}
                  className="h-6 w-6 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"
                  aria-label="Zoom out"
                >
                  <Minus className="h-3 w-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left">Zoom out (or scroll)</TooltipContent>
            </RadixTooltip>
          </div>
        )}
        {hovered && (
          <div
            className="pointer-events-none fixed z-50 rounded border border-border bg-background/95 backdrop-blur-sm px-2 py-1 text-xs shadow-sm"
            style={{ left: hovered.x + 12, top: hovered.y + 12 }}
          >
            <span className="font-medium">{hovered.name}</span>
            {hovered.count > 0 && <span className="text-muted-foreground ml-1.5">{hovered.count.toLocaleString()}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
