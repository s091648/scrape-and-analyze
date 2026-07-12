import { apiFetch } from './client'

export interface MetricDefinitionDisplay {
  metric_key: string
  label_i18n_key: string
  icon_name: string | null
  format_hint: string | null
  unit: string | null
}

// 2026-07-12: one row per metric_key (not per provider) — provider/priority extraction
// config lives in a separate maintainer-only table and is never exposed to the admin UI.
export interface MetricDefinitionAdmin extends MetricDefinitionDisplay {
  id: string
  enabled: boolean
  created_at?: string | null
  updated_at?: string | null
}

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwOnError(res: Response): Promise<Response> {
  if (!res.ok) {
    const err: any = new Error(`HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res
}

/** Public — display metadata for enabled catalog metrics only. */
export async function fetchEnabledMetricDefinitions(locale?: string): Promise<MetricDefinitionDisplay[]> {
  const res = await throwOnError(await apiFetch('/metric-definitions', {}, locale))
  return res.json()
}

/** Admin — every catalog row, including disabled ones. */
export async function fetchAllMetricDefinitions(token?: string): Promise<MetricDefinitionAdmin[]> {
  const res = await throwOnError(
    await apiFetch('/admin/metric-definitions', { headers: authHeader(token) }),
  )
  return res.json()
}

/** Admin — updates enabled and/or icon_name only; extraction/label config is not editable
 * here (FR-041). Pass only the field(s) being changed. */
export async function updateMetricDefinition(
  id: string,
  data: { enabled?: boolean; icon_name?: string },
  token?: string,
): Promise<MetricDefinitionAdmin> {
  const res = await throwOnError(
    await apiFetch(`/admin/metric-definitions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify(data),
    }),
  )
  return res.json()
}
