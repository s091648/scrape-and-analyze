import { describe, it, expect, vi } from 'vitest'

// next-auth imports next/server internally which doesn't resolve in the jsdom test environment.
vi.mock('next-auth', () => ({
  default: vi.fn((config: any) => config),
}))
vi.mock('next-auth/providers/credentials', () => ({
  default: vi.fn((opts: any) => ({ ...opts, type: 'credentials' })),
}))
vi.mock('next-auth/providers/google', () => ({
  default: vi.fn((opts) => ({ ...opts, id: opts.id ?? 'google', type: 'oauth' })),
}))

describe('authConfig', () => {
  it('has google-login and google-register providers', async () => {
    const { authConfig } = await import('@/lib/auth')
    const ids = authConfig.providers.map((p: any) => p.id)
    expect(ids).toContain('google-login')
    expect(ids).toContain('google-register')
  })

  it('has credentials provider', async () => {
    const { authConfig } = await import('@/lib/auth')
    const creds = authConfig.providers.find((p: any) => p.type === 'credentials')
    expect(creds).toBeDefined()
  })

  it('credentials authorize returns null for missing fields', async () => {
    const { authConfig } = await import('@/lib/auth')
    const provider = authConfig.providers.find((p: any) => p.type === 'credentials') as any
    const result = await provider.authorize({})
    expect(result).toBeNull()
  })

  it('session callback relays the backend-issued accessToken from the jwt token', async () => {
    vi.resetModules()
    const { authConfig } = await import('@/lib/auth')
    const session = { user: {} }
    const token = { role: 'admin', userId: 'user-id-123', exp: 9999999999, accessToken: 'backend-issued-token' }
    const result = await (authConfig.callbacks as any).session({ session, token })
    expect((result.user as any).role).toBe('admin')
    expect((result as any).accessToken).toBe('backend-issued-token')
  })

  it('jwt callback copies role, accessToken and refreshToken from user on sign-in', async () => {
    vi.resetModules()
    const { authConfig } = await import('@/lib/auth')
    const token = {}
    const user = { id: 'u1', role: 'user', accessToken: 'initial-access-token', refreshToken: 'a-refresh-token', expiresIn: 3600 }
    const result = await (authConfig.callbacks as any).jwt({ token, user })
    expect(result.role).toBe('user')
    expect(result.userId).toBe('u1')
    expect(result.accessToken).toBe('initial-access-token')
    expect(result.refreshToken).toBe('a-refresh-token')
    expect(result.accessTokenExpires).toBeGreaterThan(Date.now())
  })

  it('jwt callback reuses a still-valid accessToken without calling the backend', async () => {
    vi.resetModules()
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const { authConfig } = await import('@/lib/auth')
    const token = {
      accessToken: 'still-valid-token',
      refreshToken: 'a-refresh-token',
      accessTokenExpires: Date.now() + 60 * 60 * 1000,
    }
    const result = await (authConfig.callbacks as any).jwt({ token })
    expect(result.accessToken).toBe('still-valid-token')
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('jwt callback exchanges the refresh token for a new accessToken once expired', async () => {
    vi.resetModules()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'refreshed-access-token', expires_in: 3600 }),
    } as Response)
    const { authConfig } = await import('@/lib/auth')
    const token = {
      accessToken: 'expired-token',
      refreshToken: 'a-refresh-token',
      accessTokenExpires: Date.now() - 1000,
    }
    const result = await (authConfig.callbacks as any).jwt({ token })
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/auth/refresh'),
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ refresh_token: 'a-refresh-token' }) }),
    )
    expect(result.accessToken).toBe('refreshed-access-token')
    expect(result.accessTokenExpires).toBeGreaterThan(Date.now())
    fetchSpy.mockRestore()
  })

  it('jwt callback keeps the stale accessToken when the refresh call fails', async () => {
    vi.resetModules()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false } as Response)
    const { authConfig } = await import('@/lib/auth')
    const token = {
      accessToken: 'expired-token',
      refreshToken: 'a-refresh-token',
      accessTokenExpires: Date.now() - 1000,
    }
    const result = await (authConfig.callbacks as any).jwt({ token })
    expect(result.accessToken).toBe('expired-token')
    fetchSpy.mockRestore()
  })
})
