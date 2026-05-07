import { apiFetch } from './client'

export interface Topic {
  id: string
  name: string
  display_name: string
  color_hex: string | null
  sort_order: number | null
}

export async function fetchTopics(locale?: string): Promise<Topic[]> {
  const res = await apiFetch('/topics', {}, locale)
  const raw = await res.json()
  return Array.isArray(raw) ? raw : []
}

export async function createTopic(
  body: Pick<Topic, 'name' | 'display_name' | 'color_hex'>,
  locale?: string,
): Promise<Topic> {
  const res = await apiFetch('/topics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function updateTopic(
  id: string,
  body: Partial<Pick<Topic, 'display_name' | 'color_hex' | 'sort_order'>>,
  locale?: string,
): Promise<Topic> {
  const res = await apiFetch(`/topics/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, locale)
  return res.json()
}

export async function deleteTopic(id: string, locale?: string): Promise<void> {
  await apiFetch(`/topics/${id}`, { method: 'DELETE' }, locale)
}
