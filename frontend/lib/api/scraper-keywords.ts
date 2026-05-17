import { apiFetch } from './client'

export interface ScraperKeyword {
  id: string
  keyword: string
  keyword_type: string
  topic_id: string
}

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchScraperKeywords(
  params: { source_id?: string; topic_id?: string; keyword_type?: string },
  token?: string,
  locale?: string,
): Promise<ScraperKeyword[]> {
  const qs = new URLSearchParams()
  if (params.source_id) qs.set('source_id', params.source_id)
  if (params.topic_id) qs.set('topic_id', params.topic_id)
  if (params.keyword_type) qs.set('keyword_type', params.keyword_type)
  const res = await apiFetch(`/scraper-keywords?${qs}`, { headers: authHeader(token) }, locale)
  return res.json()
}

export async function createScraperKeyword(
  body: { keyword: string; keyword_type: string; source_id: string },
  token?: string,
  locale?: string,
): Promise<ScraperKeyword> {
  const res = await apiFetch('/scraper-keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function createTopicKeyword(
  topicId: string,
  body: { keyword: string; keyword_type: string },
  token?: string,
  locale?: string,
): Promise<ScraperKeyword> {
  const qs = new URLSearchParams({ topic_id: topicId, keyword_type: body.keyword_type })
  const res = await apiFetch(`/scraper-keywords?${qs}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function deleteScraperKeyword(id: string, token?: string, locale?: string): Promise<void> {
  await apiFetch(`/scraper-keywords/${id}`, { method: 'DELETE', headers: authHeader(token) }, locale)
}
