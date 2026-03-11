import { getSession, signOut } from 'next-auth/react'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  console.log(BACKEND_URL, path)
  const response = await fetch(`${BACKEND_URL}${path}`, options)

  if (response.status === 401) {
    const session = await getSession()
    if (session) {
      await signOut({ redirect: true, callbackUrl: '/login' })
    }
  }

  return response
}