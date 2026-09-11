import { apiFetch } from './client'

export type AnalyticsWindow = 7 | 30 | 90

export interface DailyViews {
  day: string // ISO date
  views: number
}

export interface TrendingArticle {
  article_id: string
  title: string
  source: string | null
  topic: string | null
  window_views: number
  total_views: number
  sparkline: DailyViews[]
}

export interface TopicViews {
  topic: string
  views: number
}

export interface AllTimeTopArticle {
  article_id: string
  title: string
  source: string | null
  topic: string | null
  total_views: number
}

export interface AnalyticsOverview {
  days: number
  daily_totals: DailyViews[]
  trending: TrendingArticle[]
  by_topic: TopicViews[]
  all_time_top: AllTimeTopArticle[]
}

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
