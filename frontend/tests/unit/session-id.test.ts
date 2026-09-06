import { describe, it, expect, beforeEach } from 'vitest'
import { getSessionId } from '@/lib/session-id'

const STORAGE_KEY = 'analytics_session'

beforeEach(() => {
  sessionStorage.clear()
})

describe('getSessionId', () => {
  it('mints an id and persists it', () => {
    const id = getSessionId()
    expect(id).toBeTruthy()
    const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY)!)
    expect(stored.id).toBe(id)
    expect(typeof stored.lastSeen).toBe('number')
  })

  it('returns the same id on subsequent calls within the idle window', () => {
    expect(getSessionId()).toBe(getSessionId())
  })

  it('slides lastSeen forward on each call', async () => {
    getSessionId()
    const first = JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).lastSeen
    await new Promise(r => setTimeout(r, 5))
    getSessionId()
    const second = JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).lastSeen
    expect(second).toBeGreaterThanOrEqual(first)
  })

  it('mints a fresh id once the stored session has been idle past 30 minutes', () => {
    const oldId = getSessionId()
    const stale = { id: oldId, lastSeen: Date.now() - 31 * 60 * 1000 }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stale))
    expect(getSessionId()).not.toBe(oldId)
  })

  it('recovers from a corrupt stored value', () => {
    sessionStorage.setItem(STORAGE_KEY, 'not json')
    expect(getSessionId()).toBeTruthy()
  })
})
