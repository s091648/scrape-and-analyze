import { apiFetch } from './client'
import { authHeaders } from './auth'

export interface NotificationSettings {
  email_enabled: boolean
  telegram_chat_id: string | null
  telegram_enabled: boolean
  locale: string
}

export async function getFavorites(token: string): Promise<{ article_ids: string[] }> {
  const res = await apiFetch('/user/favorites', { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function addFavorite(articleId: string, token: string): Promise<void> {
  await apiFetch(`/user/favorites/${articleId}`, { method: 'POST', headers: authHeaders(token) })
}

export async function removeFavorite(articleId: string, token: string): Promise<void> {
  await apiFetch(`/user/favorites/${articleId}`, { method: 'DELETE', headers: authHeaders(token) })
}

export async function fetchSubscriptions(token: string): Promise<{ topic_ids: string[] }> {
  const res = await apiFetch('/user/subscriptions', { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function subscribeToTopic(topicId: string, token: string): Promise<void> {
  await apiFetch('/user/subscriptions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ topic_id: topicId }),
  })
}

export async function unsubscribeTopic(topicId: string, token: string): Promise<void> {
  await apiFetch(`/user/subscriptions/${topicId}`, { method: 'DELETE', headers: authHeaders(token) })
}

export async function fetchNotificationSettings(token: string): Promise<NotificationSettings> {
  const res = await apiFetch('/user/notification-settings', { headers: authHeaders(token) })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function updateNotificationSettings(settings: Partial<NotificationSettings>, token: string): Promise<NotificationSettings> {
  const res = await apiFetch('/user/notification-settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(settings),
  }, undefined, { silent: true })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}
