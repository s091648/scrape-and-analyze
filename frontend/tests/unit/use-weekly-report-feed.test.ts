import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useWeeklyReportFeed } from '@/hooks/use-weekly-report-feed'
import type { WeeklyReport } from '@/lib/api/weekly-reports'

const mockFetchLatest = vi.fn()
const mockFetchReports = vi.fn()
const mockFetchWeeks = vi.fn()
const mockFetchByWeek = vi.fn()
vi.mock('@/lib/api/weekly-reports', () => ({
  fetchLatestWeeklyReport: (...args: any[]) => mockFetchLatest(...args),
  fetchWeeklyReports: (...args: any[]) => mockFetchReports(...args),
  fetchWeeklyReportWeeks: (...args: any[]) => mockFetchWeeks(...args),
  fetchWeeklyReportByWeek: (...args: any[]) => mockFetchByWeek(...args),
}))

function _report(week: string): WeeklyReport {
  return {
    id: week, topic_id: 't1', week_start_date: `${week}T00:00:00Z`, title: 'W',
    summary_text: 's', cover_image_url: null, article_count: 1, status: 'ok',
    created_at: null, sources: [],
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchLatest.mockResolvedValue(_report('2026-09-07'))
  mockFetchReports.mockResolvedValue({ items: [_report('2026-09-07')], total: 1, page: 1, size: 10 })
  mockFetchWeeks.mockResolvedValue(['2026-09-07'])
  mockFetchByWeek.mockResolvedValue(_report('2026-08-31'))
})

describe('useWeeklyReportFeed', () => {
  it('does not fetch when disabled, or when topicId is null', () => {
    const a = renderHook(
      () => useWeeklyReportFeed({ enabled: false, topicId: 't1' }),
      { wrapper: createSWRTestWrapper() },
    )
    expect(a.result.current.data).toBeUndefined()

    const b = renderHook(
      () => useWeeklyReportFeed({ enabled: true, topicId: null }),
      { wrapper: createSWRTestWrapper() },
    )
    expect(b.result.current.data).toBeUndefined()
    expect(mockFetchLatest).not.toHaveBeenCalled()
  })

  it('does not fetch the deep link when no initialWeek is given', async () => {
    const { result } = renderHook(
      () => useWeeklyReportFeed({ enabled: true, topicId: 't1' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.deepLinkedReport).toBeNull()
    expect(mockFetchByWeek).not.toHaveBeenCalled()
  })

  it('does not fetch the deep link when initialWeek is already present in the list', async () => {
    const { result } = renderHook(
      () => useWeeklyReportFeed({ enabled: true, topicId: 't1', initialWeek: '2026-09-07' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.deepLinkedReport).toBeNull()
    expect(mockFetchByWeek).not.toHaveBeenCalled()
  })

  it('fetches the deep-linked week when it is missing from the list', async () => {
    const { result } = renderHook(
      () => useWeeklyReportFeed({ enabled: true, topicId: 't1', initialWeek: '2026-08-31' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data?.deepLinkedReport).not.toBeNull())
    expect(mockFetchByWeek).toHaveBeenCalledWith('t1', '2026-08-31', undefined)
    expect(result.current.data?.deepLinkedReport?.id).toBe('2026-08-31')
  })

  it('reports=null (distinct from an empty list) when the list fetch itself rejects', async () => {
    mockFetchReports.mockRejectedValue(new Error('list down'))
    const { result } = renderHook(
      () => useWeeklyReportFeed({ enabled: true, topicId: 't1' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.reports).toBeNull()
    expect(result.current.data?.latest).not.toBeNull()
  })
})
