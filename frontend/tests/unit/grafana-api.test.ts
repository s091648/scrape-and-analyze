import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('next-auth/react', () => ({
  getSession: vi.fn().mockResolvedValue({ accessToken: 'test-token' }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
})

describe('queryMetrics', () => {
  it('calls /api/proxy/grafana/metrics with correct params and auth header', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ status: 'success', data: { resultType: 'matrix', result: [] } }),
    })

    const { queryMetrics } = await import('@/lib/api/grafana')
    await queryMetrics({ query: 'scraper_runs_total', start: 1000, end: 2000, step: '60' })

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/proxy/grafana/metrics')
    expect(url).toContain('query=scraper_runs_total')
    expect(url).toContain('start=1000')
    expect(url).toContain('end=2000')
    expect(url).toContain('step=60')
    expect((options?.headers as Record<string, string>)?.Authorization).toBe('Bearer test-token')
  })
})

describe('queryLogs', () => {
  it('calls /api/proxy/grafana/logs with correct params', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ status: 'success', data: { resultType: 'streams', result: [] } }),
    })

    const { queryLogs } = await import('@/lib/api/grafana')
    await queryLogs({ query: '{app="scraper"}', limit: 50 })

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/proxy/grafana/logs')
    expect(url).toContain('query=')
    expect(url).toContain('limit=50')
  })
})

describe('queryTraces', () => {
  it('calls /api/proxy/grafana/traces', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ traces: [] }),
    })

    const { queryTraces } = await import('@/lib/api/grafana')
    await queryTraces({ q: '{ .service.name = "scrape-analyzer" }', limit: 10 })

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/proxy/grafana/traces')
    expect(url).toContain('limit=10')
  })

  it('calls /api/proxy/grafana/traces without query when not provided', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ traces: [] }),
    })

    const { queryTraces } = await import('@/lib/api/grafana')
    await queryTraces()

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/proxy/grafana/traces')
    expect(url).not.toContain('q=')
  })
})

describe('queryLogsBatch', () => {
  it('calls POST /api/proxy/grafana/logs/batch with items as JSON body', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => [{ status: 'success', data: { resultType: 'streams', result: [] } }],
    })

    const { queryLogsBatch } = await import('@/lib/api/grafana')
    await queryLogsBatch([{ query: '{app="scraper"}', limit: 10 }])

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/proxy/grafana/logs/batch')
    expect(options?.method).toBe('POST')
    expect(options?.headers).toMatchObject({ 'Content-Type': 'application/json' })
    const body = JSON.parse(options?.body as string)
    expect(body).toEqual([{ query: '{app="scraper"}', limit: 10 }])
  })
})

describe('queryTracesBatch', () => {
  it('calls POST /api/proxy/grafana/traces/batch with items as JSON body', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => [{ traces: [] }],
    })

    const { queryTracesBatch } = await import('@/lib/api/grafana')
    await queryTracesBatch([{ q: '{ .service.name = "scrape-analyzer" }', limit: 20 }])

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/proxy/grafana/traces/batch')
    expect(options?.method).toBe('POST')
    const body = JSON.parse(options?.body as string)
    expect(body).toEqual([{ q: '{ .service.name = "scrape-analyzer" }', limit: 20 }])
  })
})

describe('queryMetricsBatch', () => {
  it('calls POST /api/proxy/grafana/metrics/batch with items as JSON body', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => [{ status: 'success', data: { resultType: 'matrix', result: [] } }],
    })

    const { queryMetricsBatch } = await import('@/lib/api/grafana')
    await queryMetricsBatch([{ query: 'scraper_runs_total', step: '3600' }])

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/proxy/grafana/metrics/batch')
    expect(options?.method).toBe('POST')
    expect(options?.headers).toMatchObject({ 'Content-Type': 'application/json' })
    const body = JSON.parse(options?.body as string)
    expect(body).toEqual([{ query: 'scraper_runs_total', step: '3600' }])
  })

  it('wraps a non-array response in an array', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ status: 'success', data: { resultType: 'matrix', result: [] } }),
    })

    const { queryMetricsBatch } = await import('@/lib/api/grafana')
    const result = await queryMetricsBatch([{ query: 'q' }])
    expect(Array.isArray(result)).toBe(true)
  })
})

describe('queryLokiMetricsBatch', () => {
  it('calls POST /api/proxy/grafana/loki-metrics/batch', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => [{ status: 'success', data: { resultType: 'matrix', result: [] } }],
    })

    const { queryLokiMetricsBatch } = await import('@/lib/api/grafana')
    await queryLokiMetricsBatch([
      { query: 'sum(count_over_time({app="scraper"}[1h]))', step: '3600' },
    ])

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/proxy/grafana/loki-metrics/batch')
    expect(options?.method).toBe('POST')
    expect(options?.headers).toMatchObject({ 'Content-Type': 'application/json' })
    const body = JSON.parse(options?.body as string)
    expect(body[0].query).toContain('count_over_time')
  })

  it('returns a Prometheus-compatible array response', async () => {
    const matrix = { status: 'success', data: { resultType: 'matrix', result: [{ metric: {}, values: [[1748000000, '5']] }] } }
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => [matrix],
    })

    const { queryLokiMetricsBatch } = await import('@/lib/api/grafana')
    const result = await queryLokiMetricsBatch([{ query: 'q' }])
    expect(result[0].data?.resultType).toBe('matrix')
  })
})

describe('queryTraceById', () => {
  it('calls GET /api/proxy/grafana/traces/{id}', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ batches: [] }),
    })

    const { queryTraceById } = await import('@/lib/api/grafana')
    await queryTraceById('abc123def456')

    expect(global.fetch).toHaveBeenCalledOnce()
    const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/proxy/grafana/traces/abc123def456')
    expect(options?.method).toBeUndefined()
    expect((options?.headers as Record<string, string>)?.Authorization).toBe('Bearer test-token')
  })

  it('returns an OtlpTraceResponse with batches', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ batches: [{ resource: { attributes: [] }, scopeSpans: [] }] }),
    })

    const { queryTraceById } = await import('@/lib/api/grafana')
    const result = await queryTraceById('trace1')
    expect(Array.isArray(result.batches)).toBe(true)
  })
})