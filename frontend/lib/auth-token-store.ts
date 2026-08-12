/**
 * 018-public-api-auth: a tiny module-level store so `apiFetch` (a plain async
 * function, not a hook) can read the current bearer token synchronously.
 * `AuthTokenProvider` is the sole writer — it keeps this in sync with the
 * resolved token (real NextAuth session token when logged in, otherwise the
 * guest access token). This lets every existing `apiFetch` call site benefit
 * from automatic auth without threading a `token` param through each one.
 *
 * `isLoading` additionally tracks whether AuthTokenProvider has finished its
 * *first* resolution yet (real session vs. guest bootstrap). Before that,
 * `currentToken` being `undefined` doesn't mean "no token" — it means "don't
 * know yet". apiFetch() awaits `waitForToken()` before sending any request,
 * closing the race where a component fires a request before a token exists,
 * gets a 401 from `require_any_token`, and apiFetch's 401 handler forces a
 * real signOut() even though the user's actual session was valid the whole
 * time (see git history around 3f33f0a / 5d61d84 / 37cd0b8 for the prior,
 * per-call-site attempts at this same race — this centralizes the fix so a
 * new call site can't reintroduce it).
 */
let currentToken: string | undefined
let isLoading = true
let waiters: Array<() => void> = []

// Safety net only — AuthTokenProvider is mounted at the app root (lib/providers/index.tsx)
// and always resolves isLoading to false, so this should never actually fire.
const READY_TIMEOUT_MS = 5000

export function getCurrentToken(): string | undefined {
  return currentToken
}

export function setCurrentToken(token: string | undefined, loading: boolean): void {
  currentToken = token
  const wasLoading = isLoading
  isLoading = loading
  if (wasLoading && !loading) {
    waiters.forEach(resolve => resolve())
    waiters = []
  }
}

/** Resolves once AuthTokenProvider has finished its first token resolution
 * (or after a safety timeout), whichever comes first. */
export function waitForToken(): Promise<void> {
  if (!isLoading) return Promise.resolve()
  return new Promise(resolve => {
    const timer = setTimeout(resolve, READY_TIMEOUT_MS)
    waiters.push(() => {
      clearTimeout(timer)
      resolve()
    })
  })
}
