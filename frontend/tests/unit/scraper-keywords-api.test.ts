import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('scraper-keywords API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  describe('fetchScraperKeywords', () => {
    it('fetches with empty params (no query fields)', async () => {
      mockOk([])
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      const result = await fetchScraperKeywords({})
      expect(mockApiFetch).toHaveBeenCalledWith(
        expect.stringContaining('/scraper-keywords?'),
        expect.any(Object),
        undefined,
      )
      expect(result).toEqual([])
    })

    it('includes source_id in query string', async () => {
      mockOk([])
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      await fetchScraperKeywords({ source_id: 's1' }, token)
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('source_id=s1')
    })

    it('includes topic_id and keyword_type in query string', async () => {
      mockOk([])
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      await fetchScraperKeywords({ topic_id: 't1', keyword_type: 'arxiv' }, token)
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('topic_id=t1')
      expect(url).toContain('keyword_type=arxiv')
    })

    it('passes auth header when token is provided', async () => {
      mockOk([])
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      await fetchScraperKeywords({ source_id: 's1' }, token)
      expect(mockApiFetch.mock.calls[0][1].headers).toEqual({ Authorization: `Bearer ${token}` })
    })

    it('passes no auth header when token is omitted', async () => {
      mockOk([])
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      await fetchScraperKeywords({})
      expect(mockApiFetch.mock.calls[0][1].headers).toEqual({})
    })

    it('returns keyword list from json response', async () => {
      const keywords = [{ id: 'k1', keyword: 'ti:"digital twin"', keyword_type: 'arxiv', topic_id: 't1' }]
      mockOk(keywords)
      const { fetchScraperKeywords } = await import('@/lib/api/scraper-keywords')
      const result = await fetchScraperKeywords({})
      expect(result).toEqual(keywords)
    })
  })

  describe('createScraperKeyword', () => {
    it('posts keyword with auth header and returns created keyword', async () => {
      const created = { id: 'k2', keyword: 'abs:robot', keyword_type: 'arxiv', topic_id: 't1' }
      mockOk(created)
      const { createScraperKeyword } = await import('@/lib/api/scraper-keywords')
      const body = { keyword: 'abs:robot', keyword_type: 'arxiv', source_id: 's1' }
      const result = await createScraperKeyword(body, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/scraper-keywords', expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        }),
        body: JSON.stringify(body),
      }), undefined)
      expect(result).toEqual(created)
    })

    it('passes locale as third argument', async () => {
      mockOk({})
      const { createScraperKeyword } = await import('@/lib/api/scraper-keywords')
      await createScraperKeyword({ keyword: 'x', keyword_type: 'arxiv', source_id: 's1' }, token, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), expect.any(Object), 'zh-TW')
    })
  })

  describe('createTopicKeyword', () => {
    it('posts to /scraper-keywords with topic_id and keyword_type as query params', async () => {
      const created = { id: 'k3', keyword: 'neural', keyword_type: 'openalex', topic_id: 't2' }
      mockOk(created)
      const { createTopicKeyword } = await import('@/lib/api/scraper-keywords')
      const result = await createTopicKeyword('t2', { keyword: 'neural', keyword_type: 'openalex' }, token)
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('/scraper-keywords?')
      expect(url).toContain('topic_id=t2')
      expect(url).toContain('keyword_type=openalex')
      expect(mockApiFetch.mock.calls[0][1]).toMatchObject({
        method: 'POST',
        headers: expect.objectContaining({ Authorization: `Bearer ${token}` }),
        body: JSON.stringify({ keyword: 'neural', keyword_type: 'openalex' }),
      })
      expect(result).toEqual(created)
    })
  })

  describe('deleteScraperKeyword', () => {
    it('sends DELETE to /scraper-keywords/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { deleteScraperKeyword } = await import('@/lib/api/scraper-keywords')
      await deleteScraperKeyword('k1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/scraper-keywords/k1', expect.objectContaining({
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      }), undefined)
    })
  })
})
