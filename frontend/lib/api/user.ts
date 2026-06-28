import { apiFetch } from './client'

export interface NotificationSettings {
  email_enabled: boolean
  telegram_chat_id: string | null
  telegram_enabled: boolean
  locale: string
}

export async function getFavorites(): Promise<{ article_ids: string[] }> {
  const res = await apiFetch('/user/favorites')
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function addFavorite(articleId: string): Promise<void> {
  await apiFetch(`/user/favorites/${articleId}`, { method: 'POST' })
}

export async function removeFavorite(articleId: string): Promise<void> {
  await apiFetch(`/user/favorites/${articleId}`, { method: 'DELETE' })
}

export async function fetchSubscriptions(): Promise<{ topic_ids: string[] }> {
  const res = await apiFetch('/user/subscriptions')
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function subscribeToTopic(topicId: string): Promise<void> {
  await apiFetch('/user/subscriptions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_id: topicId }),
  })
}

export async function unsubscribeTopic(topicId: string): Promise<void> {
  await apiFetch(`/user/subscriptions/${topicId}`, { method: 'DELETE' })
}

export async function fetchNotificationSettings(): Promise<NotificationSettings> {
  const res = await apiFetch('/user/notification-settings')
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export async function updateNotificationSettings(settings: Partial<NotificationSettings>): Promise<NotificationSettings> {
  const res = await apiFetch('/user/notification-settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}
