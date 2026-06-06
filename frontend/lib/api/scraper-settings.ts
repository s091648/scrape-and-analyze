import { apiFetch } from './client'

export interface ScraperSource {
  id: string
  source_type: 'rss' | 'blog' | 'arxiv' | 'semantic_scholar' | 'openalex'
  name: string
  url: string
  frequency: number
  is_active: boolean
  selector_config?: Record<string, unknown> | null
  last_scraped_at?: string | null
  activity?: number[]
}

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchScraperSources(
  topicId: string,
  token?: string,
  locale?: string,
): Promise<ScraperSource[]> {
  const res = await apiFetch(
    `/scraper-settings?topic_id=${topicId}`,
    { headers: authHeader(token) },
    locale,
  )
  return res.json()
}

export async function createScraperSource(
  body: Omit<ScraperSource, 'id' | 'last_scraped_at' | 'activity'> & { topic_id: string },
  token?: string,
  locale?: string,
): Promise<ScraperSource> {
  const res = await apiFetch('/scraper-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function updateScraperSource(
  id: string,
  body: Partial<Omit<ScraperSource, 'id'>>,
  token?: string,
  locale?: string,
): Promise<ScraperSource> {
  const res = await apiFetch(`/scraper-settings/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function deleteScraperSource(id: string, token?: string, locale?: string): Promise<void> {
  await apiFetch(`/scraper-settings/${id}`, { method: 'DELETE', headers: authHeader(token) }, locale)
}
