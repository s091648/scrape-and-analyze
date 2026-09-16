import { apiFetch } from './client'
import type { components } from './generated-types'

// source_type is widened to `string` on the response schema (FastAPI can't narrow an
// enum on an output model here) — restore the same union ScraperSettingCreate already
// uses, since existing consumers switch/compare on the literal values.
export type ScraperSource = Omit<components['schemas']['ScraperSettingOut'], 'source_type'> & {
  source_type: components['schemas']['ScraperSettingCreate']['source_type']
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
