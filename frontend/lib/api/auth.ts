import { apiFetch } from './client'

export interface UserProfile {
  id: string
  username: string
  email: string
  icon: string | null
  role: string
}

export async function fetchMe(token: string, locale?: string): Promise<UserProfile | null> {
  const res = await apiFetch('/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  }, locale)
  if (!res.ok) return null
  return res.json()
}
