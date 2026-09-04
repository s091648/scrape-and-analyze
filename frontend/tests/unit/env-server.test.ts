import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// env.server.ts reads process.env.* at module top-level, so each case needs a
// fresh module instance (vi.resetModules + dynamic import) to see a different
// stubbed value — 025-iac-provisioning US5.
describe('env.server', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('reads BACKEND_URL from process.env', async () => {
    vi.stubEnv('BACKEND_URL', 'http://backend:8000')
    const { BACKEND_URL } = await import('@/lib/env.server')
    expect(BACKEND_URL).toBe('http://backend:8000')
  })

  it('is undefined when unset, with no baked-in default', async () => {
    vi.stubEnv('BACKEND_URL', '')
    const { BACKEND_URL } = await import('@/lib/env.server')
    expect(BACKEND_URL).toBe('')
  })

  it('reads NEXTAUTH_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET', async () => {
    vi.stubEnv('NEXTAUTH_SECRET', 'shh')
    vi.stubEnv('GOOGLE_CLIENT_ID', 'client-id')
    vi.stubEnv('GOOGLE_CLIENT_SECRET', 'client-secret')
    const env = await import('@/lib/env.server')
    expect(env.NEXTAUTH_SECRET).toBe('shh')
    expect(env.GOOGLE_CLIENT_ID).toBe('client-id')
    expect(env.GOOGLE_CLIENT_SECRET).toBe('client-secret')
  })
})
