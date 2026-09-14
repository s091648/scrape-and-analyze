import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useGraphData } from '@/hooks/use-graph-data'

const mockFetchAnalysesGraph = vi.fn()
vi.mock('@/lib/api/graph', () => ({
  fetchAnalysesGraph: (...args: any[]) => mockFetchAnalysesGraph(...args),
}))

const filters = { topicId: 't1' } as any

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useGraphData', () => {
  it('does not fetch when enabled is false, even with filters set', () => {
    const { result } = renderHook(
      () => useGraphData({ enabled: false, filters, locale: 'en' }),
      { wrapper: createSWRTestWrapper() },
    )

    expect(result.current.data).toBeUndefined()
    expect(mockFetchAnalysesGraph).not.toHaveBeenCalled()
  })

  it('does not fetch when filters is null, even when enabled', () => {
    const { result } = renderHook(
      () => useGraphData({ enabled: true, filters: null }),
      { wrapper: createSWRTestWrapper() },
    )

    expect(result.current.data).toBeUndefined()
    expect(mockFetchAnalysesGraph).not.toHaveBeenCalled()
  })

  it('fetches and defaults to locale "en" when none is passed', async () => {
    mockFetchAnalysesGraph.mockResolvedValue({ nodes: [], edges: [] })
    const { result } = renderHook(
      () => useGraphData({ enabled: true, filters }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(mockFetchAnalysesGraph).toHaveBeenCalledWith(filters, undefined)
  })

  it('fetches with the given locale when passed', async () => {
    mockFetchAnalysesGraph.mockResolvedValue({ nodes: [], edges: [] })
    const { result } = renderHook(
      () => useGraphData({ enabled: true, filters, locale: 'zh-TW' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(mockFetchAnalysesGraph).toHaveBeenCalledWith(filters, 'zh-TW')
  })
})
