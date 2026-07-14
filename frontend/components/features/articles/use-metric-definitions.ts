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

/** Drops the cached display metadata so the next mount of useMetricDefinitions() refetches.
 * Call after an admin edit (icon_name/enabled) — components already mounted won't pick up the
 * change until they remount (e.g. a client-side navigation to /articles), same as `enabled`'s
 * existing behavior; this only fixes the "edit, then navigate" case, not live cross-tab push. */
export function invalidateMetricDefinitionsCache() {
  cache = null
  inFlight = null
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
