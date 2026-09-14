import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useFilterOptions } from '@/hooks/use-filter-options'

const mockFetchSourceCategories = vi.fn()
const mockFetchOriginalSources = vi.fn()
const mockFetchTagGroups = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticleFilterOriginalSources: (...args: any[]) => mockFetchOriginalSources(...args),
}))
vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: (...args: any[]) => mockFetchTagGroups(...args),
}))
vi.mock('@/lib/api/source-categories', () => ({
  fetchSourceCategories: (...args: any[]) => mockFetchSourceCategories(...args),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchSourceCategories.mockResolvedValue({ aggregator: ['a1'] })
  mockFetchOriginalSources.mockResolvedValue(['s1'])
  mockFetchTagGroups.mockResolvedValue([{ id: 'g1', name: 'Group' }])
})

describe('useFilterOptions', () => {
  it('fetches with no topicId/locale passed (key defaults to null/"en")', async () => {
    const { result } = renderHook(() => useFilterOptions(), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.aggregatorOptions).toEqual(['a1']))
    expect(mockFetchOriginalSources).toHaveBeenCalledWith(undefined, undefined)
  })

  it('all three lists populate together when every fetch resolves', async () => {
    const { result } = renderHook(() => useFilterOptions('t1', 'zh-TW'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.aggregatorOptions).toEqual(['a1'])
    expect(result.current.originalSourceOptions).toEqual(['s1'])
    expect(result.current.tagGroupOptions).toEqual([{ id: 'g1', name: 'Group' }])
  })

  it('falls back to an empty aggregatorOptions when fetchSourceCategories rejects, without blanking the others', async () => {
    mockFetchSourceCategories.mockRejectedValue(new Error('categories down'))
    const { result } = renderHook(() => useFilterOptions('t1', 'en'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.aggregatorOptions).toEqual([])
    expect(result.current.originalSourceOptions).toEqual(['s1'])
    expect(result.current.tagGroupOptions).toEqual([{ id: 'g1', name: 'Group' }])
  })

  it('falls back to an empty originalSourceOptions when that fetch rejects, without blanking the others', async () => {
    mockFetchOriginalSources.mockRejectedValue(new Error('sources down'))
    const { result } = renderHook(() => useFilterOptions('t1', 'en'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.originalSourceOptions).toEqual([])
    expect(result.current.aggregatorOptions).toEqual(['a1'])
    expect(result.current.tagGroupOptions).toEqual([{ id: 'g1', name: 'Group' }])
  })

  it('falls back to an empty tagGroupOptions when fetchTagGroups rejects, without blanking the others', async () => {
    mockFetchTagGroups.mockRejectedValue(new Error('tags down'))
    const { result } = renderHook(() => useFilterOptions('t1', 'en'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.tagGroupOptions).toEqual([])
    expect(result.current.aggregatorOptions).toEqual(['a1'])
    expect(result.current.originalSourceOptions).toEqual(['s1'])
  })
})
