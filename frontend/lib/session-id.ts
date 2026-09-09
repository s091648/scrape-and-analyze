/**
 * Per-visit session identifier, attached as the `X-Session-Id` header on every
 * `apiFetch()` call (see lib/api/client.ts). It exists so the backend's per-request
 * Loki logs (`event="request"`, backend/middleware/logging.py) and the frontend proxy
 * logs (`event="proxy_request"`, app/api/proxy/[...path]/route.ts) can be grouped into
 * one continuous visit — `user_id` alone is either absent (logged-out) or a *permanent*
 * per-visitor fingerprint (guest tokens), neither of which delimits a single visit.
 *
 * Definition of a "session" here: one browser tab, until it is either closed or left
 * idle for longer than SESSION_IDLE_MS. Stored in `sessionStorage` (per-tab, survives
 * reload, gone on tab close) alongside a last-seen timestamp that slides forward on
 * every read; once the gap exceeds the idle window a fresh id is minted. This mirrors
 * the sessionization every analytics/RUM tool does (GA's 30-minute default included) so
 * a tab left open overnight starts a new session instead of one that lasts for days.
 */

const STORAGE_KEY = 'analytics_session'
const SESSION_IDLE_MS = 30 * 60 * 1000

interface StoredSession {
  id: string
  lastSeen: number
}

function newId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    // Older/locked-down browsers without crypto.randomUUID — a collision here only
    // costs two visits sharing a session id in the logs, so a weak fallback is fine.
    return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  }
}

function read(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredSession>
    if (typeof parsed.id !== 'string' || typeof parsed.lastSeen !== 'number') return null
    return { id: parsed.id, lastSeen: parsed.lastSeen }
  } catch {
    return null
  }
}

function write(session: StoredSession): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  } catch {
    // sessionStorage unavailable (private mode, quota, disabled) — getSessionId()
    // still returns a usable per-call id below, it just won't persist across requests.
  }
}

/**
 * Returns the current session id, minting (and persisting) a new one when there is no
 * stored session or the stored one has been idle past SESSION_IDLE_MS. Safe to call
 * during SSR — returns an empty string on the server, where there is no visit to track.
 */
export function getSessionId(): string {
  if (typeof window === 'undefined') return ''
  const now = Date.now()
  const existing = read()
  if (existing && now - existing.lastSeen <= SESSION_IDLE_MS) {
    write({ id: existing.id, lastSeen: now })
    return existing.id
  }
  const id = newId()
  write({ id, lastSeen: now })
  return id
}
