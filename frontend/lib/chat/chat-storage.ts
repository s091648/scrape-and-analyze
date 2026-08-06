import type { Message } from '@s091648/chatbot-plugin-ui'

type StorageKind = 'local' | 'session'

// `kind` (not the Storage object itself) is deliberate: a caller passing `localStorage` /
// `sessionStorage` directly as an argument forces that global identifier to be evaluated at the
// call site — including during Next.js SSR, where it doesn't exist and throws
// `ReferenceError: localStorage is not defined`. Resolving the actual storage object only here,
// after the `typeof window === 'undefined'` guard, keeps the reference client-only.
function resolveStorage(kind: StorageKind): Storage {
  return kind === 'local' ? window.localStorage : window.sessionStorage
}

/** Loads a userId-tagged message history from localStorage or sessionStorage. Discards the
 * stored entry if it belongs to a different user (prevents guest→auth carry-over, or one user's
 * history leaking to the next). */
export function loadChatMessages(kind: StorageKind, key: string, userId: string): Message[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = resolveStorage(kind).getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (parsed.userId !== userId) return []
    return Array.isArray(parsed.messages)
      ? parsed.messages.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }))
      : []
  } catch {
    return []
  }
}

export function saveChatMessages(kind: StorageKind, key: string, userId: string, messages: Message[]): void {
  if (typeof window === 'undefined') return
  try {
    resolveStorage(kind).setItem(key, JSON.stringify({ userId, messages }))
  } catch {}
}
