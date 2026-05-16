import { describe, it, expect, vi } from 'vitest'

// next-auth imports next/server internally which doesn't resolve in the jsdom test environment.
vi.mock('next-auth', () => ({
  default: (config: any) => config,
}))

vi.mock('next-auth/providers/google', () => ({
  default: vi.fn((opts) => ({ ...opts, id: opts.id ?? 'google', type: 'oauth' })),
}))

vi.mock('jose', () => {
  function MockSignJWT(this: any) {}
  MockSignJWT.prototype.setProtectedHeader = function () { return this }
  MockSignJWT.prototype.setIssuedAt = function () { return this }
  MockSignJWT.prototype.setExpirationTime = function () { return this }
  MockSignJWT.prototype.sign = async () => 'mock-access-token'
  return { SignJWT: MockSignJWT }
})

describe('authConfig', () => {
  it('has google-login and google-register providers', async () => {
    const { authConfig } = await import('../lib/auth')
    const ids = authConfig.providers.map((p: any) => p.id)
    expect(ids).toContain('google-login')
    expect(ids).toContain('google-register')
  })

  it('has credentials provider', async () => {
    const { authConfig } = await import('../lib/auth')
    const creds = authConfig.providers.find((p: any) => p.type === 'credentials')
    expect(creds).toBeDefined()
  })

  it('credentials authorize returns null for missing fields', async () => {
    const { authConfig } = await import('../lib/auth')
    const provider = authConfig.providers.find((p: any) => p.type === 'credentials') as any
    const result = await provider.authorize({})
    expect(result).toBeNull()
  })

  it('session callback sets role and accessToken', async () => {
    vi.resetModules()
    const { authConfig } = await import('../lib/auth')
    const session = { user: {} }
    const token = { role: 'admin', sub: 'user-id-123', exp: 9999999999 }
    const result = await (authConfig.callbacks as any).session({ session, token })
    expect((result.user as any).role).toBe('admin')
    expect((result as any).accessToken).toBeDefined()
    expect(typeof (result as any).accessToken).toBe('string')
  })

  it('jwt callback copies role from user', async () => {
    vi.resetModules()
    const { authConfig } = await import('../lib/auth')
    const token = {}
    const user = { id: 'u1', role: 'user' }
    const result = await (authConfig.callbacks as any).jwt({ token, user })
    expect(result.role).toBe('user')
    expect(result.userId).toBe('u1')
  })
})
