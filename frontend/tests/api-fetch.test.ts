import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockSignOut = vi.fn()
const mockGetSession = vi.fn()

vi.mock('next-auth/react', () => ({
  signOut: mockSignOut,
  getSession: mockGetSession,
}))

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
})

describe('apiFetch', () => {
  it('calls signOut when 401 and active session exists', async () => {
    mockGetSession.mockResolvedValue({ user: { role: 'admin' } })
    ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

    const { apiFetch } = await import('../lib/api-fetch')
    await apiFetch('/articles')

    expect(mockSignOut).toHaveBeenCalledWith({
      redirect: true,
      callbackUrl: '/login',
    })
  })

  it('does not call signOut when 401 but no session', async () => {
    mockGetSession.mockResolvedValue(null)
    ;(global.fetch as any).mockResolvedValue({ status: 401, ok: false })

    const { apiFetch } = await import('../lib/api-fetch')
    await apiFetch('/articles')

    expect(mockSignOut).not.toHaveBeenCalled()
  })
})