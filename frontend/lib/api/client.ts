import { getSession, signOut } from 'next-auth/react'
import { toast } from 'sonner'
import * as Sentry from '@sentry/browser'
import { getCurrentToken, waitForToken } from '../auth-token-store'
import { getSessionId } from '../session-id'

// 1 initial attempt + up to 3 retries, exponential backoff with jitter. Retries
// only network failures and 429/5xx — a 4xx (other than the 401 case handled
// separately below) is a deterministic rejection a retry can't fix. Note: this
// applies to every apiFetch call regardless of HTTP method, so a POST/PUT/DELETE
// whose response is lost after the write actually succeeded server-side could
// be resent — none of today's call sites are non-idempotent in a way that's
// unsafe to double-apply (tag/topic writes are idempotent updates, article-view
// increments already dedupe server-side), but keep that in mind before pointing
// this at a genuinely non-idempotent endpoint in the future.
const MAX_ATTEMPTS = 4
const RETRY_BASE_DELAY_MS = 300
// No caller currently passes its own AbortSignal (grep confirms zero use of `signal` across
// lib/api), and nothing routed through apiFetch is a long-lived stream (chat completions use
// their own raw fetch, not this wrapper) — so a single fixed per-attempt budget is enough. A
// hung backend would otherwise block the caller indefinitely, same failure mode fixed in
// lib/server/ssr-fetch.ts.
const REQUEST_TIMEOUT_MS = 15_000

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || status >= 500
}

/** Merges the per-attempt timeout with a caller-supplied signal (if `init.signal` is ever set)
 * so this wrapper can't silently override a caller's own cancellation. */
function timeoutSignal(callerSignal: AbortSignal | null | undefined): AbortSignal {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS)
  return callerSignal ? AbortSignal.any([callerSignal, timeout]) : timeout
}

async function fetchWithRetry(url: string, init: RequestInit): Promise<Response> {
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const isLastAttempt = attempt === MAX_ATTEMPTS - 1
    try {
      const response = await fetch(url, { ...init, signal: timeoutSignal(init.signal) })
      if (response.ok || !isRetryableStatus(response.status) || isLastAttempt) {
        return response
      }
    } catch (err) {
      // A caller-initiated cancellation is a deliberate stop, not a failure to retry.
      if (init.signal?.aborted) throw err
      if (isLastAttempt) throw err
    }
    await sleep(RETRY_BASE_DELAY_MS * 2 ** attempt + Math.random() * 100)
  }
  // Unreachable — the loop always returns or throws on its last attempt.
  throw new Error('fetchWithRetry: exhausted attempts without returning')
}

export interface ApiFetchOptions {
  /** Suppress the automatic error toast (e.g. a component renders its own
   * inline error message for this call instead). Default: false — errors
   * toast automatically so no call site fails silently by default. This does
   * NOT affect Sentry reporting (see apiFetch) — that's an ops concern,
   * independent of the UX decision for any given call site. */
  silent?: boolean
}

/** Backend's central exception handler always responds with this shape on
 * error (backend/schemas/error.py::ErrorResponse) — see
 * site/guide/architecture/exception-handling.md. */
interface ParsedErrorBody {
  code?: string
  message?: string
  request_id?: string
}

function parseErrorBody(body: unknown): ParsedErrorBody {
  return (body as { error?: ParsedErrorBody } | null)?.error ?? {}
}

function extractErrorMessage(parsed: ParsedErrorBody, status: number): string {
  return parsed.message || `Request failed (${status})`
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  locale?: string,
  { silent = false }: ApiFetchOptions = {},
): Promise<Response> {
  // Closes the race where a request fires before AuthTokenProvider has resolved
  // a real session or guest token — see auth-token-store.ts. Resolves immediately
  // once a token (or "definitely no token") is already known.
  await waitForToken()

  let url = `/api/proxy${path}`

  if (locale) {
    const separator = path.includes('?') ? '&' : '?'
    url = `${url}${separator}lang=${locale}`
  }

  // 018-public-api-auth: most endpoints now require *some* valid token. Callers
  // that already set their own Authorization header (e.g. an explicit admin
  // token) keep it as-is; everyone else transparently gets the current
  // session/guest token from AuthTokenProvider, so existing call sites don't
  // each need to be updated individually.
  const headers = new Headers(options.headers)
  if (!headers.has('Authorization')) {
    const token = getCurrentToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  // Per-visit id so backend request logs and proxy logs can be grouped into one
  // session in Loki — see lib/session-id.ts. Forwarded verbatim by the proxy route.
  if (!headers.has('X-Session-Id')) {
    const sessionId = getSessionId()
    if (sessionId) headers.set('X-Session-Id', sessionId)
  }

  const response = await fetchWithRetry(url, { ...options, headers })

  if (response.status === 401) {
    const session = await getSession()
    if (session) {
      await signOut({ redirect: true, callbackUrl: '/login' })
    }
  } else if (!response.ok) {
    // Fire-and-forget: don't block the caller (which still gets the raw
    // Response to inspect/parse itself). .clone() so the body stream is
    // still readable by the caller afterwards.
    response
      .clone()
      .json()
      .then(body => parseErrorBody(body))
      .catch(() => ({}) as ParsedErrorBody)
      .then(parsed => {
        if (!silent) toast.error(extractErrorMessage(parsed, response.status))
        // Mirrors backend/exceptions/handlers.py's own policy (only 500/502
        // are Sentry-reported there): expected 4xx responses aren't bugs, so
        // only report real backend failures here too — regardless of
        // `silent`, since that flag is a UX choice, not an ops one. Tagging
        // request_id/code lets a Sentry issue be pivoted straight to the
        // matching backend log line in Loki.
        if (response.status >= 500) {
          Sentry.captureException(new Error(extractErrorMessage(parsed, response.status)), {
            tags: { path, status: response.status, code: parsed.code, request_id: parsed.request_id },
          })
        }
      })
  }

  return response
}
