/**
 * 018-public-api-auth: a tiny module-level store so `apiFetch` (a plain async
 * function, not a hook) can read the current bearer token synchronously.
 * `AuthTokenProvider` is the sole writer — it keeps this in sync with the
 * resolved token (real NextAuth session token when logged in, otherwise the
 * guest access token). This lets every existing `apiFetch` call site benefit
 * from automatic auth without threading a `token` param through each one.
 */
let currentToken: string | undefined

export function getCurrentToken(): string | undefined {
  return currentToken
}

export function setCurrentToken(token: string | undefined): void {
  currentToken = token
}
