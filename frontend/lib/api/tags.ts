import { apiFetch } from './client'

export interface TagOut {
  id: string
  name: string
  article_count: number
}

export interface SimilarGroupOut {
  id: string
  similarity_score: number
}

export interface TagGroupOut {
  id: string
  name: string
  display_name: string
  description: string | null
  color_hex: string | null
  topic_id: string
  tags: TagOut[]
  similar_groups: SimilarGroupOut[]
}

export interface TagGroupCreate {
  name: string
  display_name: string
  topic_id: string
  color_hex?: string
  description?: string
}

export interface TagGroupUpdate {
  name?: string
  display_name?: string
  color_hex?: string
  description?: string
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

export async function fetchTagGroup(groupId: string): Promise<TagGroupOut> {
  const res = await apiFetch(`/tag-groups/${groupId}`)
  if (!res.ok) throw new Error('Failed to fetch tag group')
  return res.json()
}

export async function fetchTagGroups(
  topicId?: string,
  includeSimilarity?: boolean,
): Promise<TagGroupOut[]> {
  const params = new URLSearchParams()
  if (topicId) params.set('topic_id', topicId)
  if (includeSimilarity) params.set('include_similarity', 'true')
  const query = params.toString() ? `?${params}` : ''
  const res = await apiFetch(`/tag-groups${query}`)
  const raw = await res.json()
  return Array.isArray(raw) ? raw : []
}

export async function createTagGroup(body: TagGroupCreate, token: string): Promise<TagGroupOut> {
  const res = await apiFetch('/tag-groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to create tag group')
  return res.json()
}

export async function updateTagGroup(groupId: string, body: TagGroupUpdate, token: string): Promise<TagGroupOut> {
  const res = await apiFetch(`/tag-groups/${groupId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to update tag group')
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

export async function moveTag(tagId: string, tagGroupId: string, token: string): Promise<TagOut> {
  const res = await apiFetch(`/tags/${tagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ tag_group_id: tagGroupId }),
  })
  if (!res.ok) throw new Error('Failed to move tag')
  return res.json()
}

export interface BatchMoveResult {
  succeeded: string[]
  failed: { tag_id: string; error: string }[]
}

export async function batchMoveTags(
  moves: { tag_id: string; tag_group_id: string }[],
  token: string,
): Promise<BatchMoveResult> {
  const res = await apiFetch('/tags/batch-move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(moves),
  })
  if (!res.ok) throw new Error('Failed to batch move tags')
  return res.json()
}

export interface TagGroupMergeRequest {
  group_a_id: string
  group_b_id: string
  result_name: string
  result_display_name: string
  result_color_hex?: string
  result_description?: string
}

export async function mergeTagGroups(body: TagGroupMergeRequest, token: string): Promise<TagGroupOut> {
  const res = await apiFetch('/tag-groups/merge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Failed to merge tag groups')
  return res.json()
}

export async function reorderTagGroups(
  items: { id: string; sort_order: number }[],
  token: string,
): Promise<void> {
  const res = await apiFetch('/tag-groups/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(items),
  })
  if (!res.ok) throw new Error('Failed to reorder tag groups')
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
