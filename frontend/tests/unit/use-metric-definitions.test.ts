import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const mockFetch = vi.fn()
vi.mock('@/lib/api/metric-definitions', () => ({
  fetchEnabledMetricDefinitions: (...args: any[]) => mockFetch(...args),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
})

describe('useMetricDefinitions', () => {
  it('returns metric defs keyed by metric_key after fetch resolves', async () => {
    mockFetch.mockResolvedValue([
      { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: null, unit: null },
    ])
    const { useMetricDefinitions } = await import('@/components/features/articles/use-metric-definitions')
    const { result } = renderHook(() => useMetricDefinitions())

    await waitFor(() => {
      expect(result.current['citation_count']).toBeDefined()
    })
    expect(result.current['citation_count'].icon_name).toBe('quote')
  })

  it('returns empty object before fetch resolves', async () => {
    mockFetch.mockReturnValue(new Promise(() => {})) // never resolves
    const { useMetricDefinitions } = await import('@/components/features/articles/use-metric-definitions')
    const { result } = renderHook(() => useMetricDefinitions())
    expect(result.current).toEqual({})
  })

  it('shares a single fetch across multiple mounted components (module-level cache)', async () => {
    mockFetch.mockResolvedValue([
      { metric_key: 'view_count', label_i18n_key: 'metrics.view_count', icon_name: 'eye', format_hint: null, unit: null },
    ])
    const { useMetricDefinitions } = await import('@/components/features/articles/use-metric-definitions')

    const hookA = renderHook(() => useMetricDefinitions())
    const hookB = renderHook(() => useMetricDefinitions())

    await waitFor(() => {
      expect(hookA.result.current['view_count']).toBeDefined()
      expect(hookB.result.current['view_count']).toBeDefined()
    })
    expect(mockFetch).toHaveBeenCalledTimes(1)
  })

  it('resolves to empty object when the fetch fails', async () => {
    mockFetch.mockRejectedValue(new Error('network error'))
    const { useMetricDefinitions } = await import('@/components/features/articles/use-metric-definitions')
    const { result } = renderHook(() => useMetricDefinitions())

    await waitFor(() => {
      expect(result.current).toEqual({})
    })
  })

  it('invalidateMetricDefinitionsCache causes the next mount to refetch', async () => {
    mockFetch.mockResolvedValue([
      { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: null, unit: null },
    ])
    const mod = await import('@/components/features/articles/use-metric-definitions')

    const first = renderHook(() => mod.useMetricDefinitions())
    await waitFor(() => expect(first.result.current['citation_count']).toBeDefined())
    expect(mockFetch).toHaveBeenCalledTimes(1)

    mod.invalidateMetricDefinitionsCache()

    const second = renderHook(() => mod.useMetricDefinitions())
    await waitFor(() => expect(second.result.current['citation_count']).toBeDefined())
    expect(mockFetch).toHaveBeenCalledTimes(2)
  })
})
