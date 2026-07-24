import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { pushToLoki } from '@/lib/loki-logger'

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn().mockResolvedValue({ ok: true })
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('pushToLoki', () => {
  it('returns early and does not call fetch when GRAFANA_LOKI_URL is missing', () => {
    vi.stubEnv('GRAFANA_LOKI_URL', '')
    vi.stubEnv('GRAFANA_LOKI_USER', 'user')
    vi.stubEnv('GRAFANA_API_KEY', 'key')
    pushToLoki({ level: 'info', fields: { msg: 'test' } })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('returns early when GRAFANA_LOKI_USER is missing', () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', '')
    vi.stubEnv('GRAFANA_API_KEY', 'key')
    pushToLoki({ level: 'info', fields: { msg: 'test' } })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('returns early when GRAFANA_API_KEY is missing', () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'user')
    vi.stubEnv('GRAFANA_API_KEY', '')
    pushToLoki({ level: 'info', fields: { msg: 'test' } })
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('fires fetch with POST method when all env vars are set', async () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'myuser')
    vi.stubEnv('GRAFANA_API_KEY', 'mykey')
    pushToLoki({ level: 'warn', fields: { msg: 'hello' } })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce())
    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('https://loki.example.com/push')
    expect(opts.method).toBe('POST')
    expect(opts.headers['Content-Type']).toBe('application/json')
  })

  it('uses Basic auth header with base64-encoded credentials', async () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'myuser')
    vi.stubEnv('GRAFANA_API_KEY', 'mykey')
    pushToLoki({ level: 'info', fields: {} })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce())
    const opts = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1]
    const expectedCreds = Buffer.from('myuser:mykey').toString('base64')
    expect(opts.headers['Authorization']).toBe(`Basic ${expectedCreds}`)
  })

  it('includes level and fields in the Loki stream body', async () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'u')
    vi.stubEnv('GRAFANA_API_KEY', 'k')
    pushToLoki({ level: 'error', fields: { error: 'oops', code: 500 } })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce())
    const bodyStr = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body as string
    const body = JSON.parse(bodyStr)
    expect(body.streams).toHaveLength(1)
    expect(body.streams[0].stream.level).toBe('error')
    expect(body.streams[0].stream.app).toBe('frontend')
    const logLine = JSON.parse(body.streams[0].values[0][1])
    expect(logLine.error).toBe('oops')
    expect(logLine.code).toBe(500)
    expect(logLine.level).toBe('error')
  })

  it('merges custom labels into the stream', async () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'u')
    vi.stubEnv('GRAFANA_API_KEY', 'k')
    pushToLoki({ level: 'info', labels: { service: 'api', route: '/health' }, fields: {} })
    await vi.waitFor(() => expect(global.fetch).toHaveBeenCalledOnce())
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body)
    expect(body.streams[0].stream.service).toBe('api')
    expect(body.streams[0].stream.route).toBe('/health')
  })

  it('swallows fetch errors without throwing', async () => {
    vi.stubEnv('GRAFANA_LOKI_URL', 'https://loki.example.com')
    vi.stubEnv('GRAFANA_LOKI_USER', 'u')
    vi.stubEnv('GRAFANA_API_KEY', 'k')
    ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network error'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => pushToLoki({ level: 'info', fields: {} })).not.toThrow()
    await vi.waitFor(() => expect(consoleSpy).toHaveBeenCalled())
    consoleSpy.mockRestore()
  })
})
