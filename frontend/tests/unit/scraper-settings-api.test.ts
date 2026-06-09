import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('scraper-settings API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  const sampleSource = {
    id: 's1',
    source_type: 'rss' as const,
    name: 'Test Feed',
    url: 'https://example.com/rss',
    frequency: 60,
    is_active: true,
    selector_config: null,
    last_scraped_at: null,
    activity: [],
  }

  describe('fetchScraperSources', () => {
    it('fetches sources for a topic with auth header', async () => {
      mockOk([sampleSource])
      const { fetchScraperSources } = await import('@/lib/api/scraper-settings')
      const result = await fetchScraperSources('t1', token)
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/scraper-settings?topic_id=t1',
        expect.objectContaining({ headers: { Authorization: `Bearer ${token}` } }),
        undefined,
      )
      expect(result).toEqual([sampleSource])
    })

    it('works without token (empty headers)', async () => {
      mockOk([])
      const { fetchScraperSources } = await import('@/lib/api/scraper-settings')
      await fetchScraperSources('t1')
      expect(mockApiFetch.mock.calls[0][1].headers).toEqual({})
    })

    it('passes locale as third argument', async () => {
      mockOk([])
      const { fetchScraperSources } = await import('@/lib/api/scraper-settings')
      await fetchScraperSources('t1', token, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), expect.any(Object), 'zh-TW')
    })
  })

  describe('createScraperSource', () => {
    it('posts new source with body and auth header', async () => {
      mockOk(sampleSource)
      const { createScraperSource } = await import('@/lib/api/scraper-settings')
      const body = { source_type: 'rss' as const, name: 'Test Feed', url: 'https://example.com/rss', frequency: 60, is_active: true, topic_id: 't1' }
      const result = await createScraperSource(body, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/scraper-settings', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        }),
        body: JSON.stringify(body),
      }), undefined)
      expect(result.name).toBe('Test Feed')
    })
  })

  describe('updateScraperSource', () => {
    it('patches source by id with body and auth header', async () => {
      mockOk({ ...sampleSource, is_active: false })
      const { updateScraperSource } = await import('@/lib/api/scraper-settings')
      const result = await updateScraperSource('s1', { is_active: false }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/scraper-settings/s1', expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ is_active: false }),
      }), undefined)
      expect(result.is_active).toBe(false)
    })

    it('can update frequency', async () => {
      mockOk({ ...sampleSource, frequency: 120 })
      const { updateScraperSource } = await import('@/lib/api/scraper-settings')
      await updateScraperSource('s1', { frequency: 120 }, token)
      expect(mockApiFetch.mock.calls[0][1].body).toBe(JSON.stringify({ frequency: 120 }))
    })
  })

  describe('deleteScraperSource', () => {
    it('sends DELETE to /scraper-settings/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteScraperSource } = await import('@/lib/api/scraper-settings')
      await deleteScraperSource('s1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/scraper-settings/s1', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined)
    })
  })
})
