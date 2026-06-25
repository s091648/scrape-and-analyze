import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// chat-session.ts guards typeof window === 'undefined', so we need a real
// window (jsdom provides it).  Each test gets a clean sessionStorage.

describe('chat-session', () => {
  beforeEach(() => sessionStorage.clear())

  describe('loadSession', () => {
    it('returns empty array when nothing is stored', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      expect(loadSession()).toEqual([])
    })

    it('returns parsed messages from sessionStorage', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      const messages = [
        { id: '1', role: 'user', content: 'hello', timestamp: new Date('2024-01-01').toISOString() },
      ]
      sessionStorage.setItem('rag_chat_messages', JSON.stringify(messages))
      const result = loadSession()
      expect(result).toHaveLength(1)
      expect(result[0].id).toBe('1')
      expect(result[0].role).toBe('user')
      expect(result[0].content).toBe('hello')
      expect(result[0].timestamp).toBeInstanceOf(Date)
    })

    it('returns empty array when stored value is not valid JSON', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      sessionStorage.setItem('rag_chat_messages', '{not json}')
      expect(loadSession()).toEqual([])
    })

    it('returns empty array when stored value is not an array', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      sessionStorage.setItem('rag_chat_messages', JSON.stringify({ id: '1' }))
      expect(loadSession()).toEqual([])
    })

    it('filters out entries missing required fields', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      const messages = [
        { id: '1', role: 'user', content: 'valid', timestamp: new Date().toISOString() },
        { id: 2, role: 'user', content: 'bad id' },
        { role: 'user', content: 'missing id' },
        { id: '3', content: 'missing role' },
        { id: '4', role: 'user' },
      ]
      sessionStorage.setItem('rag_chat_messages', JSON.stringify(messages))
      const result = loadSession()
      expect(result).toHaveLength(1)
      expect(result[0].id).toBe('1')
    })

    it('uses current date for entries without a timestamp', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      const messages = [{ id: '1', role: 'assistant', content: 'hi' }]
      sessionStorage.setItem('rag_chat_messages', JSON.stringify(messages))
      const before = Date.now()
      const result = loadSession()
      const after = Date.now()
      expect(result[0].timestamp.getTime()).toBeGreaterThanOrEqual(before)
      expect(result[0].timestamp.getTime()).toBeLessThanOrEqual(after)
    })

    it('returns empty array when sessionStorage is empty string', async () => {
      const { loadSession } = await import('@/lib/chat-session')
      // getItem returns null for missing keys, but an empty string is also invalid JSON
      sessionStorage.setItem('rag_chat_messages', '')
      expect(loadSession()).toEqual([])
    })
  })

  describe('saveSession', () => {
    it('writes messages to sessionStorage under the correct key', async () => {
      const { saveSession } = await import('@/lib/chat-session')
      const messages = [{ id: '1', role: 'user' as const, content: 'hi', timestamp: new Date() }]
      saveSession(messages)
      const raw = sessionStorage.getItem('rag_chat_messages')
      expect(raw).not.toBeNull()
      const parsed = JSON.parse(raw!)
      expect(parsed).toHaveLength(1)
      expect(parsed[0].id).toBe('1')
    })

    it('overwrites previously saved messages', async () => {
      const { saveSession } = await import('@/lib/chat-session')
      saveSession([{ id: '1', role: 'user' as const, content: 'first', timestamp: new Date() }])
      saveSession([{ id: '2', role: 'assistant' as const, content: 'second', timestamp: new Date() }])
      const parsed = JSON.parse(sessionStorage.getItem('rag_chat_messages')!)
      expect(parsed).toHaveLength(1)
      expect(parsed[0].id).toBe('2')
    })

    it('saves empty array when called with no messages', async () => {
      const { saveSession } = await import('@/lib/chat-session')
      saveSession([])
      expect(JSON.parse(sessionStorage.getItem('rag_chat_messages')!)).toEqual([])
    })
  })

  describe('clearSession', () => {
    it('removes the stored messages key', async () => {
      const { saveSession, clearSession } = await import('@/lib/chat-session')
      saveSession([{ id: '1', role: 'user' as const, content: 'hi', timestamp: new Date() }])
      clearSession()
      expect(sessionStorage.getItem('rag_chat_messages')).toBeNull()
    })

    it('does not throw when there is nothing to clear', async () => {
      const { clearSession } = await import('@/lib/chat-session')
      expect(() => clearSession()).not.toThrow()
    })
  })

  describe('SSR guard', () => {
    it('loadSession returns empty array when window is undefined', async () => {
      const windowSpy = vi.spyOn(globalThis, 'window', 'get').mockReturnValue(undefined as any)
      const { loadSession } = await import('@/lib/chat-session')
      expect(loadSession()).toEqual([])
      windowSpy.mockRestore()
    })

    it('saveSession does nothing when window is undefined', async () => {
      const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
      const windowSpy = vi.spyOn(globalThis, 'window', 'get').mockReturnValue(undefined as any)
      const { saveSession } = await import('@/lib/chat-session')
      saveSession([{ id: '1', role: 'user' as const, content: 'hi', timestamp: new Date() }])
      expect(setItemSpy).not.toHaveBeenCalled()
      windowSpy.mockRestore()
      setItemSpy.mockRestore()
    })

    it('clearSession does nothing when window is undefined', async () => {
      const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')
      const windowSpy = vi.spyOn(globalThis, 'window', 'get').mockReturnValue(undefined as any)
      const { clearSession } = await import('@/lib/chat-session')
      clearSession()
      expect(removeItemSpy).not.toHaveBeenCalled()
      windowSpy.mockRestore()
      removeItemSpy.mockRestore()
    })
  })
})
