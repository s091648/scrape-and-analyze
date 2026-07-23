import { getSession, signOut } from 'next-auth/react'
import { getCurrentToken } from '../auth-token-store'

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  locale?: string,
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
  }

  return response
}
