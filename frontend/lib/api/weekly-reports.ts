import { apiFetch } from './client'
import type { ArticleSource } from '@/components/features/chat/types'

export interface WeeklyReport {
  id: string
  topic_id: string | null
  week_start_date: string
  title: string
  summary_text: string
  cover_image_url: string | null
  article_count: number
  status: string
  created_at: string | null
  sources: ArticleSource[]
}

export interface PaginatedWeeklyReports {
  items: WeeklyReport[]
  total: number
  page: number
  size: number
}

export async function fetchLatestWeeklyReport(topicId: string, locale?: string): Promise<WeeklyReport | null> {
  const res = await apiFetch(`/weekly-reports/latest?topic_id=${topicId}`, {}, locale)
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
  const res = await apiFetch(`/weekly-reports/by-week?topic_id=${topicId}&week_start=${weekStart}`, {}, locale)
  if (!res.ok) return null
  const data = await res.json()
  return data ?? null
}

/** week_start_date (YYYY-MM-DD) of every completed report for the topic — drives date-picker availability. */
export async function fetchWeeklyReportWeeks(topicId: string): Promise<string[]> {
  const res = await apiFetch(`/weekly-reports/weeks?topic_id=${topicId}`)
  if (!res.ok) return []
  const data = await res.json()
  return data?.weeks ?? []
}
