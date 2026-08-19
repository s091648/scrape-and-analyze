import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => {
  vi.clearAllMocks()
})

function mockOk(data: any) {
  mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
}

describe('search API', () => {
  describe('fetchAutocompleteSuggestions', () => {
    it('builds the query string with just prefix when topic_id is omitted', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear')
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('/search/autocomplete?')
      expect(url).toContain('prefix=lear')
      expect(url).not.toContain('topic_id')
    })

    it('includes topic_id when provided', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear', 't1')
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('topic_id=t1')
    })

    it('passes locale as the third argument to apiFetch', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear', undefined, 'zh-TW')
      expect(mockApiFetch.mock.calls[0][2]).toBe('zh-TW')
    })

    it('sets the Authorization header when a token is given', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear', undefined, undefined, 'my-token')
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.headers.Authorization).toBe('Bearer my-token')
    })

    it('omits the Authorization header when no token is given', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear')
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.headers).toBeUndefined()
    })

    it('forwards the abort signal', async () => {
      mockOk({ suggestions: [] })
      const controller = new AbortController()
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear', undefined, undefined, undefined, controller.signal)
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.signal).toBe(controller.signal)
    })

    it('passes silent:true so a failed/aborted lookup does not toast', async () => {
      mockOk({ suggestions: [] })
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      await fetchAutocompleteSuggestions('lear')
      expect(mockApiFetch.mock.calls[0][3]).toEqual({ silent: true })
    })

    it('returns the parsed suggestions payload', async () => {
      const payload = { suggestions: [{ term: 'learning', occurrence_count: 5 }] }
      mockOk(payload)
      const { fetchAutocompleteSuggestions } = await import('@/lib/api/search')
      const result = await fetchAutocompleteSuggestions('lear')
      expect(result).toEqual(payload)
    })
  })

  describe('searchArticles', () => {
    it('always sets q, and omits every optional param when not provided', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'cyberattacks' })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('/search?')
      expect(url).toContain('q=cyberattacks')
      for (const absent of [
        'topic_id', 'page', 'size', 'exact_match_only', 'aggregator', 'original_source',
        'tag', 'tag_group', 'published_after', 'published_before', 'scraped_after',
        'scraped_before', 'sort', 'order',
      ]) {
        expect(url).not.toContain(`${absent}=`)
      }
    })

    it('includes topic_id, page, and size', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test', topic_id: 't1', page: 2, size: 10 })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('topic_id=t1')
      expect(url).toContain('page=2')
      expect(url).toContain('size=10')
    })

    it('sets exact_match_only=true only when the flag is true', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test', exact_match_only: true })
      expect(mockApiFetch.mock.calls[0][0] as string).toContain('exact_match_only=true')

      mockApiFetch.mockClear()
      mockOk({ items: [], total: 0 })
      await searchArticles({ q: 'test', exact_match_only: false })
      expect(mockApiFetch.mock.calls[0][0] as string).not.toContain('exact_match_only')
    })

    it('appends multiple aggregator, original_source, tag, and tag_group values', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({
        q: 'test',
        aggregator: ['techcrunch', 'arxiv'],
        original_source: ['blog.a.com'],
        tag: ['AI', 'ML'],
        tag_group: ['research'],
      })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('aggregator=techcrunch')
      expect(url).toContain('aggregator=arxiv')
      expect(url).toContain('original_source=blog.a.com')
      expect(url).toContain('tag=AI')
      expect(url).toContain('tag=ML')
      expect(url).toContain('tag_group=research')
    })

    it('includes all date range params', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({
        q: 'test',
        published_after: '2024-01-01',
        published_before: '2024-12-31',
        scraped_after: '2024-06-01',
        scraped_before: '2024-06-30',
      })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('published_after=2024-01-01')
      expect(url).toContain('published_before=2024-12-31')
      expect(url).toContain('scraped_after=2024-06-01')
      expect(url).toContain('scraped_before=2024-06-30')
    })

    it('includes sort and order only when explicitly given', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test', sort: 'published_at', order: 'asc' })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('sort=published_at')
      expect(url).toContain('order=asc')
    })

    it('passes locale as the second argument to apiFetch', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test' }, 'zh-TW')
      expect(mockApiFetch.mock.calls[0][2]).toBe('zh-TW')
    })

    it('sets the Authorization header when a token is given', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test' }, undefined, 'my-token')
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.headers.Authorization).toBe('Bearer my-token')
    })

    it('omits the Authorization header when no token is given', async () => {
      mockOk({ items: [], total: 0 })
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test' })
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.headers).toBeUndefined()
    })

    it('forwards the abort signal', async () => {
      mockOk({ items: [], total: 0 })
      const controller = new AbortController()
      const { searchArticles } = await import('@/lib/api/search')
      await searchArticles({ q: 'test' }, undefined, undefined, controller.signal)
      const init = mockApiFetch.mock.calls[0][1]
      expect(init.signal).toBe(controller.signal)
    })

    it('returns the parsed items/total payload', async () => {
      const payload = { items: [{ id: 'a1' }], total: 1 }
      mockOk(payload)
      const { searchArticles } = await import('@/lib/api/search')
      const result = await searchArticles({ q: 'test' })
      expect(result).toEqual(payload)
    })
  })
})
