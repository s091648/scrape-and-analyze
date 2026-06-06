import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock next-auth server session
const mockSession = vi.fn()

vi.mock('next-auth/next', () => ({
  getServerSession: () => mockSession(),
}))

vi.mock('@/lib/auth', () => ({
  authConfig: {},
}))

describe('GET /api/grafana-embed', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    process.env.GRAFANA_URL = 'https://grafana.example.com'
    process.env.GRAFANA_SA_TOKEN = 'sa-token-123'
    global.fetch = vi.fn()
  })

  it('returns 401 when unauthenticated', async () => {
    mockSession.mockResolvedValue(null)
    const { GET } = await import('@/app/api/grafana-embed/route')
    const req = new Request('http://localhost/api/grafana-embed?url=https://grafana.example.com/d/panel')
    const response = await GET(req as any)
    expect(response.status).toBe(401)
  })

  it('returns 403 when URL does not start with GRAFANA_URL', async () => {
    mockSession.mockResolvedValue({ user: { id: '1' } })
    const { GET } = await import('@/app/api/grafana-embed/route')
    const req = new Request('http://localhost/api/grafana-embed?url=https://evil.com/steal')
    const response = await GET(req as any)
    expect(response.status).toBe(403)
  })

  it('proxies authenticated requests with Bearer token', async () => {
    mockSession.mockResolvedValue({ user: { id: '1' } })
    ;(global.fetch as any).mockResolvedValueOnce({
      status: 200,
      body: 'test-body',
      headers: new Headers({ 'content-type': 'application/json' }),
    })
    const { GET } = await import('@/app/api/grafana-embed/route')
    const req = new Request('http://localhost/api/grafana-embed?url=https://grafana.example.com/d/panel')
    const response = await GET(req as any)
    expect(global.fetch).toHaveBeenCalledWith(
      'https://grafana.example.com/d/panel',
      expect.objectContaining({
        headers: { Authorization: 'Bearer sa-token-123' },
      })
    )
  })
})
