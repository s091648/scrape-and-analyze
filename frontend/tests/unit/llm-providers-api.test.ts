import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({
  apiFetch: mockApiFetch,
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('llm-providers API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status, json: () => Promise.resolve({}) })
  }

  describe('fetchLlmProviders', () => {
    it('fetches all providers', async () => {
      const providers = [{ id: 'p1', name: 'gemini', model: 'gemini-3-flash' }]
      mockOk(providers)
      const { fetchLlmProviders } = await import('@/lib/api/llm-providers')
      const result = await fetchLlmProviders(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers', expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }))
      expect(result).toHaveLength(1)
    })

    it('fetches without token', async () => {
      mockOk([])
      const { fetchLlmProviders } = await import('@/lib/api/llm-providers')
      await fetchLlmProviders()
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers', { headers: {} })
    })

    it('throws on HTTP error', async () => {
      mockFail(500)
      const { fetchLlmProviders } = await import('@/lib/api/llm-providers')
      await expect(fetchLlmProviders()).rejects.toThrow('HTTP 500')
    })
  })

  describe('createLlmProvider', () => {
    it('creates a provider with auth header', async () => {
      const created = { id: 'p2', name: 'claude', model: 'claude-3' }
      mockOk(created)
      const { createLlmProvider } = await import('@/lib/api/llm-providers')
      const data = { name: 'claude', model: 'claude-3', api_key_env: 'KEY', priority: 1, is_active: true, type: 'llm' as const, rpm: null, tpm: null, rpd: null }
      const result = await createLlmProvider(data, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }),
      }), undefined, { silent: true })
      expect(result.id).toBe('p2')
    })

    it('throws on HTTP error', async () => {
      mockFail(400)
      const { createLlmProvider } = await import('@/lib/api/llm-providers')
      const data = { name: 'x', model: 'x', api_key_env: 'X', priority: 1, is_active: true, type: 'llm' as const, rpm: null, tpm: null, rpd: null }
      await expect(createLlmProvider(data)).rejects.toThrow('HTTP 400')
    })
  })

  describe('updateLlmProvider', () => {
    it('patches provider with auth header', async () => {
      const updated = { id: 'p1', name: 'gemini', model: 'gemini-4' }
      mockOk(updated)
      const { updateLlmProvider } = await import('@/lib/api/llm-providers')
      const result = await updateLlmProvider('p1', { model: 'gemini-4' }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers/p1', expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
      expect(result.model).toBe('gemini-4')
    })

    it('throws on HTTP error', async () => {
      mockFail(404)
      const { updateLlmProvider } = await import('@/lib/api/llm-providers')
      await expect(updateLlmProvider('missing', {}, token)).rejects.toThrow('HTTP 404')
    })
  })

  describe('deleteLlmProvider', () => {
    it('deletes provider with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true, status: 204 })
      const { deleteLlmProvider } = await import('@/lib/api/llm-providers')
      await deleteLlmProvider('p1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers/p1', expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
      }), undefined, { silent: true })
    })

    it('throws on HTTP error', async () => {
      mockFail(404)
      const { deleteLlmProvider } = await import('@/lib/api/llm-providers')
      await expect(deleteLlmProvider('missing', token)).rejects.toThrow('HTTP 404')
    })
  })

  describe('reorderLlmProviders', () => {
    it('puts reorder with auth header', async () => {
      const reordered = [{ id: 'p1', priority: 1 }, { id: 'p2', priority: 2 }]
      mockOk(reordered)
      const { reorderLlmProviders } = await import('@/lib/api/llm-providers')
      const order = [{ id: 'p1', priority: 1 }, { id: 'p2', priority: 2 }]
      const result = await reorderLlmProviders(order, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/llm-providers/reorder', expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ order }),
      }), undefined, { silent: true })
      expect(result).toHaveLength(2)
    })

    it('throws on HTTP error', async () => {
      mockFail(400)
      const { reorderLlmProviders } = await import('@/lib/api/llm-providers')
      await expect(reorderLlmProviders([], token)).rejects.toThrow('HTTP 400')
    })
  })
})
