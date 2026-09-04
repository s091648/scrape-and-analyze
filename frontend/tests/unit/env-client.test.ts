import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// env.client.ts reads process.env.* at module top-level, so each case needs a
// fresh module instance (vi.resetModules + dynamic import) to see a different
// stubbed value — 025-iac-provisioning US5.
describe('env.client', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('reads NEXT_PUBLIC_CHAT_ENDPOINT', async () => {
    vi.stubEnv('NEXT_PUBLIC_CHAT_ENDPOINT', '/api/proxy/chat/completions')
    const env = await import('@/lib/env.client')
    expect(env.NEXT_PUBLIC_CHAT_ENDPOINT).toBe('/api/proxy/chat/completions')
  })

  it('reads APP_ENV and SENTRY_DSN (next.config.ts-whitelisted, not NEXT_PUBLIC_-prefixed)', async () => {
    vi.stubEnv('APP_ENV', 'staging')
    vi.stubEnv('SENTRY_DSN', 'https://sentry.example.com/1')
    const env = await import('@/lib/env.client')
    expect(env.APP_ENV).toBe('staging')
    expect(env.SENTRY_DSN).toBe('https://sentry.example.com/1')
  })

  it('only exports vars that are actually client-safe', async () => {
    const env = await import('@/lib/env.client')
    const exported = Object.keys(env)
    const allowed = new Set(['APP_ENV', 'SENTRY_DSN', 'NEXT_PUBLIC_CHAT_ENDPOINT'])
    for (const key of exported) {
      expect(allowed.has(key)).toBe(true)
    }
  })
})
