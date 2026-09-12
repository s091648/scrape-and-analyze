'use client'
import useSWR, { mutate } from 'swr'
import { fetchEnabledMetricDefinitions, type MetricDefinitionDisplay } from '@/lib/api/metric-definitions'

// Metric display metadata is locale-independent (label_i18n_key is a lookup key, not translated
// text) and rarely changes, so a plain string key (no params) is enough — every card on every
// page shares this one SWR cache entry instead of firing one request per card.
const METRIC_DEFINITIONS_KEY = 'metric-definitions'

/** Triggers a revalidation of the cached display metadata — call after an admin edit
 * (icon_name/enabled). Unlike the old module-level-cache version this actually pushes the
 * refreshed data to every currently-mounted `useMetricDefinitions()` caller (not just future
 * mounts) once the revalidation resolves, via SWR's normal subscriber notification. */
export function invalidateMetricDefinitionsCache() {
  void mutate(METRIC_DEFINITIONS_KEY)
}

/** Returns enabled metric display metadata keyed by metric_key, fetched once and shared via SWR. */
export function useMetricDefinitions(): Record<string, MetricDefinitionDisplay> {
  const { data } = useSWR<MetricDefinitionDisplay[]>(METRIC_DEFINITIONS_KEY, () => fetchEnabledMetricDefinitions())

  const byKey: Record<string, MetricDefinitionDisplay> = {}
  for (const d of data ?? []) byKey[d.metric_key] = d
  return byKey
}
