import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({
  apiFetch: mockApiFetch,
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('tags API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('fetchTagGroup', () => {
    it('fetches a single tag group by id', async () => {
      const group = { id: 'g1', name: 'ai', display_name: 'AI', description: null, color_hex: null, topic_id: 't1', tags: [], similar_groups: [] }
      mockOk(group)
      const { fetchTagGroup } = await import('@/lib/api/tags')
      const result = await fetchTagGroup('g1')
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups/g1', {}, undefined, { silent: true })
      expect(result.name).toBe('ai')
    })

    it('throws on failure', async () => {
      mockFail()
      const { fetchTagGroup } = await import('@/lib/api/tags')
      await expect(fetchTagGroup('g1')).rejects.toThrow('Failed to fetch tag group')
    })
  })

  describe('fetchTagGroups', () => {
    it('fetches all groups without params', async () => {
      const groups = [{ id: 'g1', name: 'ai' }]
      mockOk(groups)
      const { fetchTagGroups } = await import('@/lib/api/tags')
      const result = await fetchTagGroups()
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups')
      expect(result).toEqual(groups)
    })

    it('passes topic_id and include_similarity params', async () => {
      mockOk([])
      const { fetchTagGroups } = await import('@/lib/api/tags')
      await fetchTagGroups('topic-1', true)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups?topic_id=topic-1&include_similarity=true')
    })

    it('returns empty array when response is not an array', async () => {
      mockOk(null)
      const { fetchTagGroups } = await import('@/lib/api/tags')
      const result = await fetchTagGroups()
      expect(result).toEqual([])
    })
  })

  describe('createTagGroup', () => {
    it('posts a new tag group with auth header', async () => {
      const created = { id: 'g2', name: 'ml' }
      mockOk(created)
      const { createTagGroup } = await import('@/lib/api/tags')
      const result = await createTagGroup({ name: 'ml', display_name: 'ML', topic_id: 't1' }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
      expect(result.name).toBe('ml')
    })

    it('throws on failure', async () => {
      mockFail()
      const { createTagGroup } = await import('@/lib/api/tags')
      await expect(createTagGroup({ name: 'x', display_name: 'X', topic_id: 't1' }, token))
        .rejects.toThrow('Failed to create tag group')
    })
  })

  describe('updateTagGroup', () => {
    it('puts updated fields with auth header', async () => {
      const updated = { id: 'g1', name: 'ai_v2' }
      mockOk(updated)
      const { updateTagGroup } = await import('@/lib/api/tags')
      const result = await updateTagGroup('g1', { display_name: 'AI v2' }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups/g1', expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
      expect(result.name).toBe('ai_v2')
    })

    it('throws on failure', async () => {
      mockFail()
      const { updateTagGroup } = await import('@/lib/api/tags')
      await expect(updateTagGroup('g1', {}, token)).rejects.toThrow('Failed to update tag group')
    })
  })

  describe('deleteTagGroup', () => {
    it('deletes with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteTagGroup } = await import('@/lib/api/tags')
      await deleteTagGroup('g1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups/g1', expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
    })

    it('throws on failure', async () => {
      mockFail()
      const { deleteTagGroup } = await import('@/lib/api/tags')
      await expect(deleteTagGroup('g1', token)).rejects.toThrow('Failed to delete tag group')
    })
  })

  describe('renameTag', () => {
    it('puts name update with auth header', async () => {
      const updated = { id: 't1', name: 'new-name' }
      mockOk(updated)
      const { renameTag } = await import('@/lib/api/tags')
      const result = await renameTag('t1', 'new-name', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tags/t1', expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
      expect(result.name).toBe('new-name')
    })

    it('throws on failure', async () => {
      mockFail()
      const { renameTag } = await import('@/lib/api/tags')
      await expect(renameTag('t1', 'x', token)).rejects.toThrow('Failed to rename tag')
    })
  })

  describe('deleteTag', () => {
    it('deletes tag with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteTag } = await import('@/lib/api/tags')
      await deleteTag('t1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tags/t1', expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
    })

    it('throws on failure', async () => {
      mockFail()
      const { deleteTag } = await import('@/lib/api/tags')
      await expect(deleteTag('t1', token)).rejects.toThrow('Failed to delete tag')
    })
  })

  describe('moveTag', () => {
    it('puts tag_group_id with auth header', async () => {
      const updated = { id: 't1', name: 'tag' }
      mockOk(updated)
      const { moveTag } = await import('@/lib/api/tags')
      const result = await moveTag('t1', 'g2', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tags/t1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ tag_group_id: 'g2' }),
      }), undefined, { silent: true })
      expect(result.id).toBe('t1')
    })

    it('throws on failure', async () => {
      mockFail()
      const { moveTag } = await import('@/lib/api/tags')
      await expect(moveTag('t1', 'g2', token)).rejects.toThrow('Failed to move tag')
    })
  })

  describe('batchMoveTags', () => {
    it('posts batch moves with auth header', async () => {
      const batchResult = { succeeded: ['t1'], failed: [] }
      mockOk(batchResult)
      const { batchMoveTags } = await import('@/lib/api/tags')
      const moves = [{ tag_id: 't1', tag_group_id: 'g2' }]
      const result = await batchMoveTags(moves, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tags/batch-move', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify(moves),
      }), undefined, { silent: true })
      expect(result.succeeded).toEqual(['t1'])
    })

    it('throws on failure', async () => {
      mockFail()
      const { batchMoveTags } = await import('@/lib/api/tags')
      await expect(batchMoveTags([], token)).rejects.toThrow('Failed to batch move tags')
    })
  })

  describe('mergeTagGroups', () => {
    it('posts merge request with auth header', async () => {
      const merged = { id: 'g3', name: 'merged' }
      mockOk(merged)
      const { mergeTagGroups } = await import('@/lib/api/tags')
      const body = { group_a_id: 'g1', group_b_id: 'g2', result_name: 'merged', result_display_name: 'Merged' }
      const result = await mergeTagGroups(body, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups/merge', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify(body),
      }), undefined, { silent: true })
      expect(result.name).toBe('merged')
    })

    it('throws on failure', async () => {
      mockFail()
      const { mergeTagGroups } = await import('@/lib/api/tags')
      await expect(mergeTagGroups({ group_a_id: 'g1', group_b_id: 'g2', result_name: 'x', result_display_name: 'X' }, token))
        .rejects.toThrow('Failed to merge tag groups')
    })
  })

  describe('reorderTagGroups', () => {
    it('posts reorder with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { reorderTagGroups } = await import('@/lib/api/tags')
      const items = [{ id: 'g1', sort_order: 0 }, { id: 'g2', sort_order: 1 }]
      await reorderTagGroups(items, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-groups/reorder', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify(items),
      }), undefined, { silent: true })
    })

    it('throws on failure', async () => {
      mockFail()
      const { reorderTagGroups } = await import('@/lib/api/tags')
      await expect(reorderTagGroups([], token)).rejects.toThrow('Failed to reorder tag groups')
    })
  })

  describe('fetchPendingSuggestions', () => {
    it('fetches suggestions with auth header', async () => {
      const suggestions = [{ id: 's1', new_tag_name: 'ai', existing_tag_name: 'AI' }]
      mockOk(suggestions)
      const { fetchPendingSuggestions } = await import('@/lib/api/tags')
      const result = await fetchPendingSuggestions(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-normalization-suggestions', expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }))
      expect(result).toHaveLength(1)
    })

    it('throws on failure', async () => {
      mockFail()
      const { fetchPendingSuggestions } = await import('@/lib/api/tags')
      await expect(fetchPendingSuggestions(token)).rejects.toThrow('Failed to fetch suggestions')
    })
  })

  describe('approveSuggestion', () => {
    it('posts approve with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { approveSuggestion } = await import('@/lib/api/tags')
      await approveSuggestion('s1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-normalization-suggestions/s1/approve', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }))
    })

    it('throws on failure', async () => {
      mockFail()
      const { approveSuggestion } = await import('@/lib/api/tags')
      await expect(approveSuggestion('s1', token)).rejects.toThrow('Failed to approve suggestion')
    })
  })

  describe('approveSuggestionsBatch', () => {
    it('posts all ids in one request with auth header', async () => {
      const batchResult = { succeeded: ['s1', 's2'], failed: [] }
      mockOk(batchResult)
      const { approveSuggestionsBatch } = await import('@/lib/api/tags')
      const result = await approveSuggestionsBatch(['s1', 's2'], token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-normalization-suggestions/approve-batch', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify(['s1', 's2']),
      }))
      expect(result).toEqual(batchResult)
    })

    it('throws on failure', async () => {
      mockFail()
      const { approveSuggestionsBatch } = await import('@/lib/api/tags')
      await expect(approveSuggestionsBatch([], token)).rejects.toThrow('Failed to batch approve suggestions')
    })
  })

  describe('rejectSuggestion', () => {
    it('posts reject with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { rejectSuggestion } = await import('@/lib/api/tags')
      await rejectSuggestion('s1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tag-normalization-suggestions/s1/reject', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }))
    })

    it('throws on failure', async () => {
      mockFail()
      const { rejectSuggestion } = await import('@/lib/api/tags')
      await expect(rejectSuggestion('s1', token)).rejects.toThrow('Failed to reject suggestion')
    })
  })

  // ── T032: moveTag with null group_id (ungrouping) ──────────────────────────

  describe('moveTag with null group_id', () => {
    it('sends ungroup: true when group_id is null', async () => {
      const updated = { id: 't1', name: 'tag' }
      mockOk(updated)
      const { moveTag } = await import('@/lib/api/tags')
      const result = await moveTag('t1', null, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/tags/t1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ ungroup: true }),
      }), undefined, { silent: true })
    })
  })
})
