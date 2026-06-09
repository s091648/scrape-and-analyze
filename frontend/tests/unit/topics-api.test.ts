import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('topics API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  const sampleTopic = {
    id: 't1',
    name: 'ai',
    display_name: 'AI',
    description: null,
    color_hex: '#3b82f6',
    prompt_override: null,
    sort_order: 0,
    is_active: true,
    tag_mode: 'unsupervised' as const,
  }

  describe('fetchTopics', () => {
    it('fetches all topics without params', async () => {
      mockOk([sampleTopic])
      const { fetchTopics } = await import('@/lib/api/topics')
      const result = await fetchTopics()
      expect(mockApiFetch).toHaveBeenCalledWith('/topics', expect.any(Object), undefined)
      expect(result).toEqual([sampleTopic])
    })

    it('includes include_inactive=true in query when requested', async () => {
      mockOk([])
      const { fetchTopics } = await import('@/lib/api/topics')
      await fetchTopics({ include_inactive: true })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('include_inactive=true')
    })

    it('does not include include_inactive when false', async () => {
      mockOk([])
      const { fetchTopics } = await import('@/lib/api/topics')
      await fetchTopics({ include_inactive: false })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).not.toContain('include_inactive')
    })

    it('returns empty array when response is not an array', async () => {
      mockOk(null)
      const { fetchTopics } = await import('@/lib/api/topics')
      const result = await fetchTopics()
      expect(result).toEqual([])
    })

    it('returns empty array when response is an object', async () => {
      mockOk({ error: 'bad' })
      const { fetchTopics } = await import('@/lib/api/topics')
      const result = await fetchTopics()
      expect(result).toEqual([])
    })

    it('passes token in Authorization header', async () => {
      mockOk([])
      const { fetchTopics } = await import('@/lib/api/topics')
      await fetchTopics({}, token)
      expect(mockApiFetch.mock.calls[0][1].headers).toEqual({ Authorization: `Bearer ${token}` })
    })

    it('passes locale as third argument', async () => {
      mockOk([])
      const { fetchTopics } = await import('@/lib/api/topics')
      await fetchTopics({}, token, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), expect.any(Object), 'zh-TW')
    })
  })

  describe('createTopic', () => {
    it('posts new topic with body and auth header', async () => {
      mockOk(sampleTopic)
      const { createTopic } = await import('@/lib/api/topics')
      const body = { name: 'ai', display_name: 'AI', is_active: true }
      const result = await createTopic(body, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/topics', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        }),
        body: JSON.stringify(body),
      }), undefined)
      expect(result.name).toBe('ai')
    })

    it('supports all optional fields', async () => {
      mockOk(sampleTopic)
      const { createTopic } = await import('@/lib/api/topics')
      const body = { name: 'ml', display_name: 'ML', color_hex: '#f00', description: 'desc', prompt_override: 'override', sort_order: 1, is_active: false, tag_mode: 'supervised' as const }
      await createTopic(body, token)
      expect(mockApiFetch.mock.calls[0][1].body).toBe(JSON.stringify(body))
    })
  })

  describe('updateTopic', () => {
    it('patches topic by id with body and auth header', async () => {
      mockOk({ ...sampleTopic, display_name: 'Artificial Intelligence' })
      const { updateTopic } = await import('@/lib/api/topics')
      const result = await updateTopic('t1', { display_name: 'Artificial Intelligence' }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/topics/t1', expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ display_name: 'Artificial Intelligence' }),
      }), undefined)
      expect(result.display_name).toBe('Artificial Intelligence')
    })

    it('can toggle is_active', async () => {
      mockOk({ ...sampleTopic, is_active: false })
      const { updateTopic } = await import('@/lib/api/topics')
      await updateTopic('t1', { is_active: false }, token)
      expect(mockApiFetch.mock.calls[0][1].body).toBe(JSON.stringify({ is_active: false }))
    })
  })

  describe('deleteTopic', () => {
    it('sends DELETE to /topics/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteTopic } = await import('@/lib/api/topics')
      await deleteTopic('t1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/topics/t1', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined)
    })

    it('passes locale as third argument', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteTopic } = await import('@/lib/api/topics')
      await deleteTopic('t1', token, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), expect.any(Object), 'zh-TW')
    })
  })
})
