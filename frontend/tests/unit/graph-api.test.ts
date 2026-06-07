import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('graph API', () => {
  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  const emptyGraph = { nodes: [], edges: [] }

  describe('fetchGraph', () => {
    it('fetches graph for a topic', async () => {
      mockOk(emptyGraph)
      const { fetchGraph } = await import('@/lib/api/graph')
      const result = await fetchGraph('t1')
      expect(mockApiFetch).toHaveBeenCalledWith('/graph?topic_id=t1', {}, undefined)
      expect(result).toEqual(emptyGraph)
    })

    it('passes locale as second argument', async () => {
      mockOk(emptyGraph)
      const { fetchGraph } = await import('@/lib/api/graph')
      await fetchGraph('t1', 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith('/graph?topic_id=t1', {}, 'zh-TW')
    })
  })

  describe('fetchAnalysesGraph', () => {
    it('builds URL with topic_id', async () => {
      mockOk(emptyGraph)
      const { fetchAnalysesGraph } = await import('@/lib/api/graph')
      await fetchAnalysesGraph({ topic_id: 't1' })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('/analyses/graph?')
      expect(url).toContain('topic_id=t1')
    })

    it('includes aggregator array params', async () => {
      mockOk(emptyGraph)
      const { fetchAnalysesGraph } = await import('@/lib/api/graph')
      await fetchAnalysesGraph({ topic_id: 't1', aggregator: ['rss', 'arxiv'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('aggregator=rss')
      expect(url).toContain('aggregator=arxiv')
    })

    it('includes all date range filters', async () => {
      mockOk(emptyGraph)
      const { fetchAnalysesGraph } = await import('@/lib/api/graph')
      await fetchAnalysesGraph({
        topic_id: 't1',
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

    it('includes original_source and tag filters', async () => {
      mockOk(emptyGraph)
      const { fetchAnalysesGraph } = await import('@/lib/api/graph')
      await fetchAnalysesGraph({ topic_id: 't1', original_source: ['blog.a.com'], tag: ['ai', 'ml'] })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('original_source=blog.a.com')
      expect(url).toContain('tag=ai')
      expect(url).toContain('tag=ml')
    })

    it('passes locale as second argument', async () => {
      mockOk(emptyGraph)
      const { fetchAnalysesGraph } = await import('@/lib/api/graph')
      await fetchAnalysesGraph({ topic_id: 't1' }, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), {}, 'zh-TW')
    })
  })

  describe('fetchAnalysesGraphGroup', () => {
    it('fetches articles for a group by name', async () => {
      const articles = [{ id: 'a1', title: 'Test' }]
      mockOk(articles)
      const { fetchAnalysesGraphGroup } = await import('@/lib/api/graph')
      const result = await fetchAnalysesGraphGroup('Technology')
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/analyses/graph/group/Technology',
        {},
        undefined,
      )
      expect(result).toEqual(articles)
    })

    it('URL-encodes group names with spaces', async () => {
      mockOk([])
      const { fetchAnalysesGraphGroup } = await import('@/lib/api/graph')
      await fetchAnalysesGraphGroup('AI Research')
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('/analyses/graph/group/AI%20Research')
    })

    it('appends filters as query params when provided', async () => {
      mockOk([])
      const { fetchAnalysesGraphGroup } = await import('@/lib/api/graph')
      await fetchAnalysesGraphGroup('Tech', {
        topic_id: 't1',
        aggregator: ['rss'],
        published_after: '2024-01-01',
        published_before: '2024-12-31',
        scraped_after: '2024-06-01',
        scraped_before: '2024-06-30',
        original_source: ['blog.com'],
        tag: ['ai'],
      })
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toContain('topic_id=t1')
      expect(url).toContain('aggregator=rss')
      expect(url).toContain('published_after=2024-01-01')
      expect(url).toContain('published_before=2024-12-31')
      expect(url).toContain('scraped_after=2024-06-01')
      expect(url).toContain('scraped_before=2024-06-30')
      expect(url).toContain('original_source=blog.com')
      expect(url).toContain('tag=ai')
    })

    it('calls without query string when no filters provided', async () => {
      mockOk([])
      const { fetchAnalysesGraphGroup } = await import('@/lib/api/graph')
      await fetchAnalysesGraphGroup('Tech')
      const url = mockApiFetch.mock.calls[0][0] as string
      expect(url).toBe('/analyses/graph/group/Tech')
    })

    it('passes locale as third argument', async () => {
      mockOk([])
      const { fetchAnalysesGraphGroup } = await import('@/lib/api/graph')
      await fetchAnalysesGraphGroup('Tech', undefined, 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), {}, 'zh-TW')
    })
  })
})
