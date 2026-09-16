import { apiFetch } from './client'
import type { ArticleSource } from '@/components/features/chat/types'
import type { components } from './generated-types'

// `sources` is kept as the pre-existing ArticleSource type (shared with the chat feature)
// rather than the generated ArticleSourceOut — everything else comes from the backend
// contract so it can't silently drift.
export type WeeklyReport = Omit<components['schemas']['WeeklyReportOut'], 'sources'> & {
  sources: ArticleSource[]
}

export interface PaginatedWeeklyReports {
  items: WeeklyReport[]
  total: number
  page: number
  size: number
}

export async function fetchLatestWeeklyReport(topicId: string, locale?: string): Promise<WeeklyReport | null> {
  const res = await apiFetch(`/weekly-reports/latest?topic_id=${topicId}`, {}, locale, { silent: true })
  if (!res.ok) return null
  const data = await res.json()
  return data ?? null
}

export async function fetchWeeklyReports(topicId: string, limit = 10, offset = 0, locale?: string): Promise<PaginatedWeeklyReports> {
  const res = await apiFetch(`/weekly-reports?topic_id=${topicId}&limit=${limit}&offset=${offset}`, {}, locale)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

/** weekStart: any date within the target week (YYYY-MM-DD) — the backend normalizes to that week's Monday. */
export async function fetchWeeklyReportByWeek(topicId: string, weekStart: string, locale?: string): Promise<WeeklyReport | null> {
  const res = await apiFetch(`/weekly-reports/by-week?topic_id=${topicId}&week_start=${weekStart}`, {}, locale, { silent: true })
  if (!res.ok) return null
  const data = await res.json()
  return data ?? null
}

/** week_start_date (YYYY-MM-DD) of every completed report for the topic — drives date-picker availability. */
export async function fetchWeeklyReportWeeks(topicId: string): Promise<string[]> {
  const res = await apiFetch(`/weekly-reports/weeks?topic_id=${topicId}`, {}, undefined, { silent: true })
  if (!res.ok) return []
  const data = await res.json()
  return data?.weeks ?? []
}
