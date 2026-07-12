'use client'
import { useEffect, useState } from 'react'
import { fetchEnabledMetricDefinitions, type MetricDefinitionDisplay } from '@/lib/api/metric-definitions'

// Module-level cache: metric display metadata is locale-independent (label_i18n_key is a lookup
// key, not translated text) and rarely changes, so every card on a page shares one fetch instead
// of firing one request per card.
let cache: MetricDefinitionDisplay[] | null = null
let inFlight: Promise<MetricDefinitionDisplay[]> | null = null

function load(): Promise<MetricDefinitionDisplay[]> {
  if (cache) return Promise.resolve(cache)
  if (!inFlight) {
    inFlight = fetchEnabledMetricDefinitions()
      .then(defs => { cache = defs; return defs })
      .catch(() => { inFlight = null; return [] })
  }
  return inFlight
}

/** Returns enabled metric display metadata keyed by metric_key, fetched once and shared. */
export function useMetricDefinitions(): Record<string, MetricDefinitionDisplay> {
  const [defs, setDefs] = useState<MetricDefinitionDisplay[]>(cache ?? [])

  useEffect(() => {
    let cancelled = false
    load().then(result => {
      if (!cancelled) setDefs(result)
    })
    return () => { cancelled = true }
  }, [])

  const byKey: Record<string, MetricDefinitionDisplay> = {}
  for (const d of defs) byKey[d.metric_key] = d
  return byKey
}
