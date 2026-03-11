import { getSession, signOut } from 'next-auth/react'

export async function apiFetch(path: string, options: RequestInit = {}, proxy: boolean = true): Promise<Response> {
  const response = await fetch(`${proxy ? `/api/proxy` : ''}${path}`, options)

  if (response.status === 401) {
    const session = await getSession()
    if (session) {
      await signOut({ redirect: true, callbackUrl: '/login' })
    }
  }

  return response
}