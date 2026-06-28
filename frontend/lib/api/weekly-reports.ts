import { apiFetch } from './client'

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
}

export interface PaginatedWeeklyReports {
  items: WeeklyReport[]
  total: number
  page: number
  size: number
}

export async function fetchLatestWeeklyReport(topicId: string): Promise<WeeklyReport | null> {
  const res = await apiFetch(`/weekly-reports/latest?topic_id=${topicId}`)
  if (!res.ok) return null
  const data = await res.json()
  return data ?? null
}

export async function fetchWeeklyReports(topicId: string, limit = 10, offset = 0): Promise<PaginatedWeeklyReports> {
  const res = await apiFetch(`/weekly-reports?topic_id=${topicId}&limit=${limit}&offset=${offset}`)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}
