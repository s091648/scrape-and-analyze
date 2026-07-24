import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApiFetch = vi.fn()
vi.mock('@/lib/api/client', () => ({ apiFetch: mockApiFetch }))

beforeEach(() => vi.clearAllMocks())

describe('weekly-reports API', () => {
  function mockOk(data: any) {
    mockApiFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve(data) })
  }

  function mockFail(status = 500) {
    mockApiFetch.mockResolvedValue({ ok: false, status })
  }

  describe('fetchLatestWeeklyReport', () => {
    it('returns the report when response is ok', async () => {
      const report = { id: 'r1', title: 'Latest' }
      mockOk(report)
      const { fetchLatestWeeklyReport } = await import('@/lib/api/weekly-reports')
      const result = await fetchLatestWeeklyReport('t1')
      expect(mockApiFetch).toHaveBeenCalledWith('/weekly-reports/latest?topic_id=t1', {}, undefined, { silent: true })
      expect(result).toEqual(report)
    })

    it('returns null when data is null', async () => {
      mockOk(null)
      const { fetchLatestWeeklyReport } = await import('@/lib/api/weekly-reports')
      const result = await fetchLatestWeeklyReport('t1')
      expect(result).toBeNull()
    })

    it('returns null when response is not ok', async () => {
      mockFail(404)
      const { fetchLatestWeeklyReport } = await import('@/lib/api/weekly-reports')
      const result = await fetchLatestWeeklyReport('t1')
      expect(result).toBeNull()
    })

    it('passes locale to apiFetch', async () => {
      mockOk(null)
      const { fetchLatestWeeklyReport } = await import('@/lib/api/weekly-reports')
      await fetchLatestWeeklyReport('t1', 'zh-TW')
      expect(mockApiFetch).toHaveBeenCalledWith(expect.any(String), {}, 'zh-TW', { silent: true })
    })
  })

  describe('fetchWeeklyReports', () => {
    it('fetches with default limit/offset', async () => {
      const payload = { items: [], total: 0, page: 1, size: 10 }
      mockOk(payload)
      const { fetchWeeklyReports } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReports('t1')
      expect(mockApiFetch).toHaveBeenCalledWith('/weekly-reports?topic_id=t1&limit=10&offset=0', {}, undefined)
      expect(result).toEqual(payload)
    })

    it('fetches with custom limit/offset', async () => {
      mockOk({ items: [], total: 0, page: 1, size: 5 })
      const { fetchWeeklyReports } = await import('@/lib/api/weekly-reports')
      await fetchWeeklyReports('t1', 5, 15)
      expect(mockApiFetch).toHaveBeenCalledWith('/weekly-reports?topic_id=t1&limit=5&offset=15', {}, undefined)
    })

    it('throws with status code when response is not ok', async () => {
      mockFail(500)
      const { fetchWeeklyReports } = await import('@/lib/api/weekly-reports')
      await expect(fetchWeeklyReports('t1')).rejects.toThrow('500')
    })
  })

  describe('fetchWeeklyReportByWeek', () => {
    it('returns the report when response is ok', async () => {
      const report = { id: 'r2', title: 'Week Report' }
      mockOk(report)
      const { fetchWeeklyReportByWeek } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportByWeek('t1', '2026-06-15')
      expect(mockApiFetch).toHaveBeenCalledWith('/weekly-reports/by-week?topic_id=t1&week_start=2026-06-15', {}, undefined, { silent: true })
      expect(result).toEqual(report)
    })

    it('returns null when response is not ok', async () => {
      mockFail(404)
      const { fetchWeeklyReportByWeek } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportByWeek('t1', '2026-06-15')
      expect(result).toBeNull()
    })

    it('returns null when data is null', async () => {
      mockOk(null)
      const { fetchWeeklyReportByWeek } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportByWeek('t1', '2026-06-15')
      expect(result).toBeNull()
    })
  })

  describe('fetchWeeklyReportWeeks', () => {
    it('returns weeks array when response is ok', async () => {
      mockOk({ weeks: ['2026-06-15', '2026-06-08'] })
      const { fetchWeeklyReportWeeks } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportWeeks('t1')
      expect(mockApiFetch).toHaveBeenCalledWith('/weekly-reports/weeks?topic_id=t1', {}, undefined, { silent: true })
      expect(result).toEqual(['2026-06-15', '2026-06-08'])
    })

    it('returns empty array when response is not ok', async () => {
      mockFail(500)
      const { fetchWeeklyReportWeeks } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportWeeks('t1')
      expect(result).toEqual([])
    })

    it('returns empty array when weeks field is missing', async () => {
      mockOk({})
      const { fetchWeeklyReportWeeks } = await import('@/lib/api/weekly-reports')
      const result = await fetchWeeklyReportWeeks('t1')
      expect(result).toEqual([])
    })
  })
})
