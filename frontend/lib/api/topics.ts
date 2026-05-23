import { apiFetch } from './client'

export interface Topic {
  id: string
  name: string
  display_name: string
  description: string | null
  color_hex: string | null
  prompt_override: string | null
  sort_order: number | null
  is_active: boolean
  auto_tag_groups: boolean
}

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchTopics(
  params?: { include_inactive?: boolean },
  token?: string,
  locale?: string,
): Promise<Topic[]> {
  const qs = new URLSearchParams()
  if (params?.include_inactive) qs.set('include_inactive', 'true')
  const query = qs.toString() ? `?${qs}` : ''
  const res = await apiFetch(`/topics${query}`, { headers: authHeader(token) }, locale)
  const raw = await res.json()
  return Array.isArray(raw) ? raw : []
}

export async function createTopic(
  body: Partial<Pick<Topic, 'name' | 'display_name' | 'color_hex' | 'description' | 'prompt_override' | 'sort_order' | 'is_active'>>,
  token?: string,
  locale?: string,
): Promise<Topic> {
  const res = await apiFetch('/topics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function updateTopic(
  id: string,
  body: Partial<Omit<Topic, 'id'>>,
  token?: string,
  locale?: string,
): Promise<Topic> {
  const res = await apiFetch(`/topics/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function deleteTopic(id: string, token?: string, locale?: string): Promise<void> {
  await apiFetch(`/topics/${id}`, { method: 'DELETE', headers: authHeader(token) }, locale)
}
