import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('user API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('getFavorites', () => {
    it('returns favorites when response is ok', async () => {
      mockOk({ article_ids: ['a1', 'a2'] })
      const { getFavorites } = await import('@/lib/api/user')
      const result = await getFavorites(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/favorites', { headers: { Authorization: `Bearer ${token}` } })
      expect(result).toEqual({ article_ids: ['a1', 'a2'] })
    })

    it('throws with status code when response is not ok', async () => {
      mockFail(401)
      const { getFavorites } = await import('@/lib/api/user')
      await expect(getFavorites(token)).rejects.toThrow('401')
    })
  })

  describe('addFavorite', () => {
    it('posts to /user/favorites/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { addFavorite } = await import('@/lib/api/user')
      await addFavorite('a1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/favorites/a1', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
    })
  })

  describe('removeFavorite', () => {
    it('sends DELETE to /user/favorites/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { removeFavorite } = await import('@/lib/api/user')
      await removeFavorite('a1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/favorites/a1', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
    })
  })

  describe('fetchSubscriptions', () => {
    it('returns subscriptions when response is ok', async () => {
      mockOk({ topic_ids: ['t1'] })
      const { fetchSubscriptions } = await import('@/lib/api/user')
      const result = await fetchSubscriptions(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/subscriptions', { headers: { Authorization: `Bearer ${token}` } })
      expect(result).toEqual({ topic_ids: ['t1'] })
    })

    it('throws with status code when response is not ok', async () => {
      mockFail(500)
      const { fetchSubscriptions } = await import('@/lib/api/user')
      await expect(fetchSubscriptions(token)).rejects.toThrow('500')
    })
  })

  describe('subscribeToTopic', () => {
    it('posts topic_id body with auth and content-type headers', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { subscribeToTopic } = await import('@/lib/api/user')
      await subscribeToTopic('t1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ topic_id: 't1' }),
      })
    })
  })

  describe('unsubscribeTopic', () => {
    it('sends DELETE to /user/subscriptions/:id with auth header', async () => {
      mockApiFetch.mockResolvedValue({ ok: true })
      const { unsubscribeTopic } = await import('@/lib/api/user')
      await unsubscribeTopic('t1', token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/subscriptions/t1', {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
    })
  })

  describe('fetchNotificationSettings', () => {
    it('returns settings when response is ok', async () => {
      const settings = { email_enabled: true, telegram_chat_id: null, telegram_enabled: false, locale: 'en' }
      mockOk(settings)
      const { fetchNotificationSettings } = await import('@/lib/api/user')
      const result = await fetchNotificationSettings(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/notification-settings', { headers: { Authorization: `Bearer ${token}` } })
      expect(result).toEqual(settings)
    })

    it('throws with status code when response is not ok', async () => {
      mockFail(401)
      const { fetchNotificationSettings } = await import('@/lib/api/user')
      await expect(fetchNotificationSettings(token)).rejects.toThrow('401')
    })
  })

  describe('updateNotificationSettings', () => {
    it('sends PUT with partial body and auth/content-type headers', async () => {
      const updated = { email_enabled: false, telegram_chat_id: '123', telegram_enabled: true, locale: 'zh-TW' }
      mockOk(updated)
      const { updateNotificationSettings } = await import('@/lib/api/user')
      const result = await updateNotificationSettings({ telegram_enabled: true }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/user/notification-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ telegram_enabled: true }),
      })
      expect(result).toEqual(updated)
    })

    it('throws with status code when response is not ok', async () => {
      mockFail(500)
      const { updateNotificationSettings } = await import('@/lib/api/user')
      await expect(updateNotificationSettings({ locale: 'en' }, token)).rejects.toThrow('500')
    })
  })
})
