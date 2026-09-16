import { apiFetch } from './client'
import type { components } from './generated-types'

export type AnalyticsWindow = 7 | 30 | 90

export type DailyViews = components['schemas']['DailyViews']
export type TrendingArticle = components['schemas']['TrendingArticle']
export type TopicViews = components['schemas']['TopicViews']
export type AllTimeTopArticle = components['schemas']['AllTimeTopArticle']
export type AnalyticsOverview = components['schemas']['AnalyticsOverview']

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Admin — one payload for the whole /admin/analytics page. `days` ∈ {7, 30, 90}. */
export async function fetchAnalyticsOverview(
  days: AnalyticsWindow,
  token?: string,
): Promise<AnalyticsOverview> {
  const res = await apiFetch(
    `/admin/analytics/overview?days=${days}`,
    { headers: authHeader(token) },
    undefined,
    { silent: true },
  )
  if (!res.ok) {
    const err: Error & { status?: number } = new Error(`HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}
