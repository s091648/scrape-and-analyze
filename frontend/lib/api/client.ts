import { getSession, signOut } from 'next-auth/react'

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

  const response = await fetch(url, options)

  if (response.status === 401) {
    const session = await getSession()
    if (session) {
      await signOut({ redirect: true, callbackUrl: '/login' })
    }
  }

  return response
}
