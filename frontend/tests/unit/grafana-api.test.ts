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

    const { queryMetrics } = await import('@/lib/grafana-api')
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

    const { queryLogs } = await import('@/lib/grafana-api')
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

    const { queryTraces } = await import('@/lib/grafana-api')
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

    const { queryTraces } = await import('@/lib/grafana-api')
    await queryTraces()

    const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/proxy/grafana/traces')
    expect(url).not.toContain('q=')
  })
})
