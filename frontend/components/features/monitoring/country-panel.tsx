'use client'

import { useState } from 'react'
import { CountryMap } from './country-map'
import { CountryTable } from './country-table'
import type { PrometheusResponse } from '@/lib/api/grafana'

interface CountryPanelProps {
  mapTitle: string
  mapTooltip?: string
  tableTitle: string
  tableTooltip?: string
  height?: number
  data?: PrometheusResponse | null
  loading?: boolean
}

/** Renders CountryMap + CountryTable as two grid siblings (not wrapped in their own div, so
 * they land side by side in the parent's grid-cols-2 the same way a lone chart would) sharing
 * one selected-country state — clicking a table row pans/zooms the map to it and outlines it,
 * and clicking a shape on the map does the reverse. */
export function CountryPanel({ mapTitle, mapTooltip, tableTitle, tableTooltip, height, data, loading }: CountryPanelProps) {
  const [selected, setSelected] = useState<string | null>(null)
  return (
    <>
      <CountryMap title={mapTitle} tooltip={mapTooltip} height={height} data={data} loading={loading}
        selectedCode={selected} onSelectCountry={setSelected} />
      <CountryTable title={tableTitle} tooltip={tableTooltip} height={height} data={data} loading={loading}
        selectedCode={selected} onSelectCountry={setSelected} />
    </>
  )
}
