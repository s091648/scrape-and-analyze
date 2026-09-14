import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(async () => {
  vi.clearAllMocks()
  const { __resetViewedThisSessionForTests } = await import('@/lib/api/articles')
  __resetViewedThisSessionForTests()
})

describe('articles API', () => {
  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('fetchArticles', () => {
    it('fetches articles with empty params', async () => {
      const payload = { items: [], total: 0 }
      mockOk(payload)
      const { fetchArticles } = await import('@/lib/api/articles')
      const result = await fetchArticles({})
      expect(mockApiFetch).toHaveBeenCalledWith(expect.stringContaining('/articles?'), {}, undefined)
      expect(result).toEqual(payload)
    })

    it('includes page and size in query string', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ page: 2, size: 20 })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('page=2')
      expect(url).toContain('size=20')
    })

    it('includes topic_id, sort, order', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ topic_id: 't1', sort: 'published_at', order: 'desc' })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('topic_id=t1')
      expect(url).toContain('sort=published_at')
      expect(url).toContain('order=desc')
    })

    it('appends multiple aggregator values', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ aggregator: ['rss', 'arxiv'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('aggregator=rss')
      expect(url).toContain('aggregator=arxiv')
    })

    it('appends multiple original_source values', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ original_source: ['blog.a.com', 'blog.b.com'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('original_source=blog.a.com')
      expect(url).toContain('original_source=blog.b.com')
    })

    it('appends multiple tag and tag_group values', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ tag: ['ai', 'ml'], tag_group: ['tech'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('tag=ai')
      expect(url).toContain('tag=ml')
      expect(url).toContain('tag_group=tech')
    })

    it('appends multiple tag_id values', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({ tag_id: ['id1', 'id2'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('tag_id=id1')
      expect(url).toContain('tag_id=id2')
    })

    it('includes all date range params', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({
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

    it('passes locale as third argument', async () => {
      mockOk({ items: [], total: 0 })
      const { fetchArticles } = await import('@/lib/api/articles')
      await fetchArticles({}, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), {}, 'zh-TW')
    })
  })

  describe('fetchArticleById', () => {
    it('fetches article detail by id', async () => {
      const article = { id: 'a1', title: 'Test', tags: [], tag_groups: [], content: '', source: 'rss', url: 'http://example.com', published_at: null, scraped_at: null, pain_points: null, insights: null, innovations: null, model_used: null }
      mockOk(article)
      const { fetchArticleById } = await import('@/lib/api/articles')
      const result = await fetchArticleById('a1')
      expect(mockApiFetch).toHaveBeenCalledWith('/articles/a1', {}, undefined, { silent: undefined })
      expect(result.id).toBe('a1')
    })

    it('throws an error when response is not ok', async () => {
      mockFail(404)
      const { fetchArticleById } = await import('@/lib/api/articles')
      await expect(fetchArticleById('missing')).rejects.toThrow('404')
    })

    it('passes locale to apiFetch', async () => {
      const article = { id: 'a1', title: 'T', tags: [], tag_groups: [], content: '', source: 'rss', url: '', published_at: null, scraped_at: null, pain_points: null, insights: null, innovations: null, model_used: null }
      mockOk(article)
      const { fetchArticleById } = await import('@/lib/api/articles')
      await fetchArticleById('a1', 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith('/articles/a1', {}, 'zh-TW', { silent: undefined })
    })

    // No caching test here anymore — repeat-call dedup/caching for the same (id, locale) is now
    // owned by hooks/use-article-detail.ts's SWR hook, not this function. See its own tests.
    it('always calls apiFetch again on a repeat call — no caching at this layer', async () => {
      const article = { id: 'a1', title: 'T', tags: [], tag_groups: [], content: '', source: 'rss', url: '', published_at: null, scraped_at: null, pain_points: null, insights: null, innovations: null, model_used: null }
      mockOk(article)
      const { fetchArticleById } = await import('@/lib/api/articles')
      await fetchArticleById('a1', 'zh-TW')
      await fetchArticleById('a1', 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledTimes(2)
    })
  })

  describe('fetchArticleFilterOriginalSources', () => {
    it('fetches without topic_id', async () => {
      mockOk(['source-a'])
      const { fetchArticleFilterOriginalSources } = await import('@/lib/api/articles')
      const result = await fetchArticleFilterOriginalSources()
      expect(mockApiFetch).toHaveBeenCalledWith('/articles/filters/original-sources', {}, undefined)
      expect(result).toEqual(['source-a'])
    })

    it('appends topic_id when provided', async () => {
      mockOk([])
      const { fetchArticleFilterOriginalSources } = await import('@/lib/api/articles')
      await fetchArticleFilterOriginalSources('t1')
      expect(mockApiFetch).toHaveBeenCalledWith('/articles/filters/original-sources?topic_id=t1', {}, undefined)
    })
  })

  describe('recordArticleView', () => {
    function flushMicrotasks() {
      return new Promise(resolve => setTimeout(resolve, 0))
    }

    it('posts a view on the first call for an article id', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { recordArticleView } = await import('@/lib/api/articles')
      recordArticleView('a1')
      await flushMicrotasks()
      expect(mockApiFetch).toHaveBeenCalledWith('/articles/a1/view', { method: 'POST' }, undefined, { silent: true })
    })

    it('does not post again for the same id within the same session', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { recordArticleView } = await import('@/lib/api/articles')
      recordArticleView('a1')
      await flushMicrotasks()
      recordArticleView('a1')
      await flushMicrotasks()
      expect(mockApiFetch).toHaveBeenCalledTimes(1)
    })

    it('posts separately for a different article id', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { recordArticleView } = await import('@/lib/api/articles')
      recordArticleView('a1')
      recordArticleView('a2')
      await flushMicrotasks()
      expect(mockApiFetch).toHaveBeenCalledTimes(2)
    })

    it('retries on the next call if the POST failed', async () => {
      mockApiFetch.mockRejectedValueOnce(new Error('network error'))
      const { recordArticleView } = await import('@/lib/api/articles')
      recordArticleView('a1')
      await flushMicrotasks()
      expect(mockApiFetch).toHaveBeenCalledTimes(1)

      mockApiFetch.mockResolvedValueOnce({ ok: true })
      recordArticleView('a1')
      await flushMicrotasks()
      expect(mockApiFetch).toHaveBeenCalledTimes(2)
    })
  })
})
