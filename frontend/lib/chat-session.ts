import type { Message } from '@s091648/chatbot-plugin-ui'

const SESSION_KEY = 'rag_chat_messages'

function reviveMessage(raw: unknown): Message | null {
  if (!raw || typeof raw !== 'object') return null
  const m = raw as Record<string, unknown>
  if (typeof m.id !== 'string' || typeof m.role !== 'string' || typeof m.content !== 'string') return null
  return {
    id: m.id,
    role: m.role as Message['role'],
    content: m.content,
    timestamp: m.timestamp ? new Date(m.timestamp as string) : new Date(),
    toolCall: m.toolCall as Message['toolCall'],
    toolResult: m.toolResult as Message['toolResult'],
  }
}

export function loadSession(): Message[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(reviveMessage).filter((m): m is Message => m !== null)
  } catch {
    return []
  }
}

export function saveSession(messages: Message[]): void {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(messages))
  } catch {
    // sessionStorage might be unavailable (private browsing, quota exceeded)
  }
}

export function clearSession(): void {
  if (typeof window === 'undefined') return
  sessionStorage.removeItem(SESSION_KEY)
}
