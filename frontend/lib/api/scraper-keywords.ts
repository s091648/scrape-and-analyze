import { apiFetch } from './client'

export interface ScraperKeyword {
  id: string
  keyword: string
  keyword_type: string
  topic_id: string
}

export async function fetchScraperKeywords(
  params: { source_id?: string; keyword_type?: string },
  locale?: string,
): Promise<ScraperKeyword[]> {
  const qs = new URLSearchParams()
  if (params.source_id) qs.set('source_id', params.source_id)
  if (params.keyword_type) qs.set('keyword_type', params.keyword_type)
  const res = await apiFetch(`/scraper-keywords?${qs}`, {}, locale)
  return res.json()
}

export async function createScraperKeyword(
  body: { keyword: string; keyword_type: string; source_id: string },
  locale?: string,
): Promise<ScraperKeyword> {
  const res = await apiFetch('/scraper-keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function deleteScraperKeyword(id: string, locale?: string): Promise<void> {
  await apiFetch(`/scraper-keywords/${id}`, { method: 'DELETE' }, locale)
}
