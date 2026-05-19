import { apiFetch } from './client'

export interface TagOut {
  id: string
  name: string
  article_count: number
}

export interface TagGroupOut {
  id: string
  name: string
  display_name: string
  color_hex: string | null
  topic_id: string
  tags: TagOut[]
}

export interface SuggestionOut {
  id: string
  new_tag_id: string
  new_tag_name: string
  existing_tag_id: string
  existing_tag_name: string
  group_name: string
  similarity_score: number
  article_id: string | null
}

export async function fetchTagGroups(topicId?: string): Promise<TagGroupOut[]> {
  const qs = topicId ? `?topic_id=${topicId}` : ''
  const res = await apiFetch(`/tag-groups${qs}`)
  if (!res.ok) throw new Error('Failed to fetch tag groups')
  return res.json()
}

export async function deleteTagGroup(groupId: string, token: string): Promise<void> {
  const res = await apiFetch(`/tag-groups/${groupId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to delete tag group')
}

export async function renameTag(tagId: string, name: string, token: string): Promise<TagOut> {
  const res = await apiFetch(`/tags/${tagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw new Error('Failed to rename tag')
  return res.json()
}

export async function deleteTag(tagId: string, token: string): Promise<void> {
  const res = await apiFetch(`/tags/${tagId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to delete tag')
}

export async function fetchPendingSuggestions(token: string): Promise<SuggestionOut[]> {
  const res = await apiFetch('/tag-normalization-suggestions', {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to fetch suggestions')
  return res.json()
}

export async function approveSuggestion(suggestionId: string, token: string): Promise<void> {
  const res = await apiFetch(`/tag-normalization-suggestions/${suggestionId}/approve`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to approve suggestion')
}

export async function rejectSuggestion(suggestionId: string, token: string): Promise<void> {
  const res = await apiFetch(`/tag-normalization-suggestions/${suggestionId}/reject`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Failed to reject suggestion')
}
