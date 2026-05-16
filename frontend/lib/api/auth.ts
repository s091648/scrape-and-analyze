import { apiFetch } from './client'

export interface UserProfile {
  id: string
  username: string | null
  name: string | null
  email: string | null
  icon: string | null
  role: string
  google_id: string | null
}

export interface AdminUser {
  id: string
  email: string | null
  name: string | null
  username: string | null
  role: 'admin' | 'user'
  is_allowed: boolean
  icon: string | null
  google_id: string | null
  created_at: string | null
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` }
}

export async function fetchMe(token: string, locale?: string): Promise<UserProfile | null> {
  const res = await apiFetch('/auth/me', { headers: authHeaders(token) }, locale)
  if (!res.ok) return null
  return res.json()
}

export async function updateMe(
  token: string,
  body: Partial<Pick<UserProfile, 'name' | 'icon'>>,
  locale?: string,
): Promise<Response> {
  return apiFetch('/auth/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(body),
  }, locale)
}

export async function changePassword(
  token: string,
  body: { current_password: string; new_password: string },
  locale?: string,
): Promise<Response> {
  return apiFetch('/auth/me/password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(body),
  }, locale)
}

export async function deleteMe(token: string, locale?: string): Promise<Response> {
  return apiFetch('/auth/me', { method: 'DELETE', headers: authHeaders(token) }, locale)
}

export async function unlinkGoogle(token: string, locale?: string): Promise<Response> {
  return apiFetch('/auth/me/link-google', { method: 'DELETE', headers: authHeaders(token) }, locale)
}

export async function registerUser(
  body: { username: string; password: string; email: string; name?: string },
  locale?: string,
): Promise<Response> {
  return apiFetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, locale)
}

export async function fetchUsers(token: string, locale?: string): Promise<AdminUser[]> {
  const res = await apiFetch('/auth/users', { headers: authHeaders(token) }, locale)
  return res.json()
}

export async function updateUser(
  token: string,
  id: string,
  body: Partial<Pick<AdminUser, 'role' | 'is_allowed'>>,
  locale?: string,
): Promise<Response> {
  return apiFetch(`/auth/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(body),
  }, locale)
}

export async function deleteUser(token: string, id: string, locale?: string): Promise<Response> {
  return apiFetch(`/auth/users/${id}`, { method: 'DELETE', headers: authHeaders(token) }, locale)
}

export async function createUser(
  token: string,
  body: { email?: string; username?: string; password?: string; role: string },
  locale?: string,
): Promise<Response> {
  return apiFetch('/auth/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(body),
  }, locale)
}
