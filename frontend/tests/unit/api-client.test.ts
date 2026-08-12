import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockSignOut = vi.fn()
const mockGetSession = vi.fn()

vi.mock('next-auth/react', () => ({
  signOut: mockSignOut,
  getSession: mockGetSession,
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  global.fetch = vi.fn()
})

async function markTokenResolved(token: string | undefined = undefined) {
  const { setCurrentToken } = await import('@/lib/auth-token-store')
  setCurrentToken(token, false)
}

/** apiFetch's non-ok branch calls response.clone().json() — plain mock responses
 * need a clone() too, matching the real fetch Response shape. */
function mockResponse(status: number, ok: boolean) {
  return { status, ok, clone: () => ({ json: () => Promise.resolve({}) }) }
}

describe('apiFetch', () => {
  it('calls signOut when 401 and active session exists', async () => {
    mockGetSession.mockResolvedValue({ user: { role: 'admin' } })
    ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

    await markTokenResolved()
    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles')

    expect(mockSignOut).toHaveBeenCalledWith({
      redirect: true,
      callbackUrl: '/login',
    })
  })

  it('does not call signOut when 401 but no session', async () => {
    mockGetSession.mockResolvedValue(null)
    ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

    await markTokenResolved()
    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles')

    expect(mockSignOut).not.toHaveBeenCalled()
  })

  it('prepends /api/proxy to path by default', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    await markTokenResolved()
    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/proxy/articles'),
      expect.any(Object),
    )
  })

  it('appends lang query param when locale is provided', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    await markTokenResolved()
    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles', {}, 'zh-TW')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('lang=zh-TW'),
      expect.any(Object),
    )
  })

  // ── 018-public-api-auth: automatic token attachment ──────────────────────

  it('attaches the current token from the store when no Authorization header is set', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    await markTokenResolved('guest-token-abc')
    const { apiFetch } = await import('@/lib/api/client')

    await apiFetch('/articles')

    const [, options] = (global.fetch as any).mock.calls[0]
    expect((options.headers as Headers).get('Authorization')).toBe('Bearer guest-token-abc')
  })

  it('does not overwrite an explicitly provided Authorization header', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    await markTokenResolved('guest-token-abc')
    const { apiFetch } = await import('@/lib/api/client')

    await apiFetch('/articles', { headers: { Authorization: 'Bearer explicit-token' } })

    const [, options] = (global.fetch as any).mock.calls[0]
    expect((options.headers as Headers).get('Authorization')).toBe('Bearer explicit-token')
  })

  it('sends no Authorization header when the store has no current token', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    await markTokenResolved(undefined)
    const { apiFetch } = await import('@/lib/api/client')

    await apiFetch('/articles')

    const [, options] = (global.fetch as any).mock.calls[0]
    expect((options.headers as Headers).has('Authorization')).toBe(false)
  })

  // ── race-condition fix: apiFetch waits for AuthTokenProvider's first resolution ──

  it('does not send a request until the token store resolves (real regression: 401 → forced signOut)', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    const { setCurrentToken } = await import('@/lib/auth-token-store')
    const { apiFetch } = await import('@/lib/api/client')

    const fetchPromise = apiFetch('/articles')
    // Still "loading" — must not have fired yet.
    await Promise.resolve()
    await Promise.resolve()
    expect(global.fetch).not.toHaveBeenCalled()

    setCurrentToken('resolved-token', false)
    await fetchPromise

    expect(global.fetch).toHaveBeenCalledTimes(1)
    const [, options] = (global.fetch as any).mock.calls[0]
    expect((options.headers as Headers).get('Authorization')).toBe('Bearer resolved-token')
  })

  // ── exponential-backoff retry ─────────────────────────────────────────────

  describe('retry behavior', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })
    afterEach(() => {
      vi.useRealTimers()
    })

    it('retries a 500 up to 3 times then returns the last response', async () => {
      ;(global.fetch as any).mockResolvedValue(mockResponse(500, false))

      await markTokenResolved()
      const { apiFetch } = await import('@/lib/api/client')

      const resultPromise = apiFetch('/articles', {}, undefined, { silent: true })
      await vi.runAllTimersAsync()
      const result = await resultPromise

      expect(global.fetch).toHaveBeenCalledTimes(4) // 1 initial + 3 retries
      expect(result.status).toBe(500)
    })

    it('retries a network failure and succeeds if a later attempt works', async () => {
      ;(global.fetch as any)
        .mockRejectedValueOnce(new TypeError('network error'))
        .mockResolvedValueOnce({ status: 200, ok: true })

      await markTokenResolved()
      const { apiFetch } = await import('@/lib/api/client')

      const resultPromise = apiFetch('/articles')
      await vi.runAllTimersAsync()
      const result = await resultPromise

      expect(global.fetch).toHaveBeenCalledTimes(2)
      expect(result.ok).toBe(true)
    })

    it('does not retry a 404', async () => {
      ;(global.fetch as any).mockResolvedValue(mockResponse(404, false))

      await markTokenResolved()
      const { apiFetch } = await import('@/lib/api/client')

      const resultPromise = apiFetch('/articles/does-not-exist', {}, undefined, { silent: true })
      await vi.runAllTimersAsync()
      const result = await resultPromise

      expect(global.fetch).toHaveBeenCalledTimes(1)
      expect(result.status).toBe(404)
    })

    it('does not retry a 401 (handled by the signOut path, not the retry loop)', async () => {
      mockGetSession.mockResolvedValue(null)
      ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

      await markTokenResolved()
      const { apiFetch } = await import('@/lib/api/client')

      const resultPromise = apiFetch('/articles')
      await vi.runAllTimersAsync()
      await resultPromise

      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })
})
