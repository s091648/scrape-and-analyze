import { getSession, signOut } from 'next-auth/react'

export async function apiFetch(path: string, options: RequestInit = {}, proxy: boolean = true): Promise<Response> {
  // Get stored locale and add as query param
  const locale = typeof window !== 'undefined' ? localStorage.getItem('locale') : null

  let url = `${proxy ? `/api/proxy` : ''}${path}`
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