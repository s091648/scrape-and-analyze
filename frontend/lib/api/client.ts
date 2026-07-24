import { getSession, signOut } from 'next-auth/react'
import { toast } from 'sonner'
import * as Sentry from '@sentry/browser'
import { getCurrentToken } from '../auth-token-store'

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

  const response = await fetch(url, { ...options, headers })

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
