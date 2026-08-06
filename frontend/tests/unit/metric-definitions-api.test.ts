import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('metric-definitions API', () => {
  const token = 'test-token'

  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('fetchEnabledMetricDefinitions', () => {
    it('returns display metadata when response is ok', async () => {
      const defs = [{ metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: null, unit: null }]
      mockOk(defs)
      const { fetchEnabledMetricDefinitions } = await import('@/lib/api/metric-definitions')
      const result = await fetchEnabledMetricDefinitions()
      expect(mockApiFetch).toHaveBeenCalledWith('/metric-definitions', {}, undefined)
      expect(result).toEqual(defs)
    })

    it('passes locale to apiFetch', async () => {
      mockOk([])
      const { fetchEnabledMetricDefinitions } = await import('@/lib/api/metric-definitions')
      await fetchEnabledMetricDefinitions('zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith('/metric-definitions', {}, 'zh-TW')
    })

    it('throws with status attached when response is not ok', async () => {
      mockFail(500)
      const { fetchEnabledMetricDefinitions } = await import('@/lib/api/metric-definitions')
      await expect(fetchEnabledMetricDefinitions()).rejects.toMatchObject({ status: 500, message: 'HTTP 500' })
    })
  })

  describe('fetchAllMetricDefinitions', () => {
    it('fetches admin list with auth header when token provided', async () => {
      mockOk([])
      const { fetchAllMetricDefinitions } = await import('@/lib/api/metric-definitions')
      await fetchAllMetricDefinitions(token)
      expect(mockApiFetch).toHaveBeenCalledWith('/admin/metric-definitions', { headers: { Authorization: `Bearer ${token}` } })
    })

    it('fetches with empty headers when no token provided', async () => {
      mockOk([])
      const { fetchAllMetricDefinitions } = await import('@/lib/api/metric-definitions')
      await fetchAllMetricDefinitions()
      expect(mockApiFetch).toHaveBeenCalledWith('/admin/metric-definitions', { headers: {} })
    })

    it('throws with status attached when response is not ok', async () => {
      mockFail(403)
      const { fetchAllMetricDefinitions } = await import('@/lib/api/metric-definitions')
      await expect(fetchAllMetricDefinitions(token)).rejects.toMatchObject({ status: 403 })
    })
  })

  describe('updateMetricDefinition', () => {
    it('sends PATCH with body and auth header', async () => {
      const updated = { id: 'm1', metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'trophy', format_hint: null, unit: null, enabled: true }
      mockOk(updated)
      const { updateMetricDefinition } = await import('@/lib/api/metric-definitions')
      const result = await updateMetricDefinition('m1', { icon_name: 'trophy' }, token)
      expect(mockApiFetch).toHaveBeenCalledWith('/admin/metric-definitions/m1', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ icon_name: 'trophy' }),
      }, undefined, { silent: true })
      expect(result).toEqual(updated)
    })

    it('throws with status attached when response is not ok', async () => {
      mockFail(422)
      const { updateMetricDefinition } = await import('@/lib/api/metric-definitions')
      await expect(updateMetricDefinition('m1', { enabled: false }, token)).rejects.toMatchObject({ status: 422 })
    })
  })
})
