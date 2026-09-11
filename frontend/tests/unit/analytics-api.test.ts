import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('analytics API', () => {
  const overview = {
    days: 30,
    daily_totals: [],
    trending: [],
    by_topic: [],
    all_time_top: [],
  }

  describe('fetchAnalyticsOverview', () => {
    it('builds the overview URL with the given days window', async () => {
      mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(overview) })
      const { fetchAnalyticsOverview } = await import('@/lib/api/analytics')
      const result = await fetchAnalyticsOverview(30)
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/admin/analytics/overview?days=30',
        { headers: {} },
        undefined,
        { silent: true },
      )
      expect(result).toEqual(overview)
    })

    it('passes an Authorization header when a token is given', async () => {
      mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(overview) })
      const { fetchAnalyticsOverview } = await import('@/lib/api/analytics')
      await fetchAnalyticsOverview(7, 'test-token')
      expect(mockApiFetch).toHaveBeenCalledWith(
        '/admin/analytics/overview?days=7',
        { headers: { Authorization: 'Bearer test-token' } },
        undefined,
        { silent: true },
      )
    })

    it('throws an error carrying the HTTP status when the response is not ok', async () => {
      mockApiFetch.mockResolvedValue({ ok: false, status: 403 })
      const { fetchAnalyticsOverview } = await import('@/lib/api/analytics')
      await expect(fetchAnalyticsOverview(90)).rejects.toMatchObject({
        message: 'HTTP 403',
        status: 403,
      })
    })
  })
})
