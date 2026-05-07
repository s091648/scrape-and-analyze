import { describe, it, expect, vi, beforeEach } from 'vitest'

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

describe('apiFetch', () => {
  it('calls signOut when 401 and active session exists', async () => {
    mockGetSession.mockResolvedValue({ user: { role: 'admin' } })
    ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

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

    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles')

    expect(mockSignOut).not.toHaveBeenCalled()
  })

  it('prepends /api/proxy to path by default', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/proxy/articles'),
      expect.any(Object),
    )
  })

  it('appends lang query param when locale is provided', async () => {
    ;(global.fetch as any).mockResolvedValue({ status: 200, ok: true })

    const { apiFetch } = await import('@/lib/api/client')
    await apiFetch('/articles', {}, 'zh-TW')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('lang=zh-TW'),
      expect.any(Object),
    )
  })
})
