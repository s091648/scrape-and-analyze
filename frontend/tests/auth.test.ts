import { describe, it, expect, vi } from 'vitest'

describe('NextAuth config', () => {
  it('authorize returns null for invalid credentials', async () => {
    const { authConfig } = await import('../lib/auth')
    const provider = authConfig.providers[0] as any
    const result = await provider.authorize({ username: 'bad', password: 'wrong' })
    expect(result).toBeNull()
  })
})