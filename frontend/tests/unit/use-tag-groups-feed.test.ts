import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useTagGroupsFeed } from '@/hooks/use-tag-groups-feed'

const mockFetchTagGroups = vi.fn()
const mockFetchPendingSuggestions = vi.fn()
vi.mock('@/lib/api/tags', () => ({
  fetchTagGroups: (...args: any[]) => mockFetchTagGroups(...args),
  fetchPendingSuggestions: (...args: any[]) => mockFetchPendingSuggestions(...args),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockFetchTagGroups.mockResolvedValue([{ id: 'g1', name: 'Group' }])
  mockFetchPendingSuggestions.mockResolvedValue([{ id: 'sg1' }])
})

describe('useTagGroupsFeed', () => {
  it('does not fetch when disabled', () => {
    const { result } = renderHook(
      () => useTagGroupsFeed({ enabled: false, includeSimilarity: false, isAdmin: false }),
      { wrapper: createSWRTestWrapper() },
    )

    expect(result.current.data).toBeUndefined()
    expect(mockFetchTagGroups).not.toHaveBeenCalled()
  })

  it('fetches with topicId/token omitted (key defaults to null)', async () => {
    const { result } = renderHook(
      () => useTagGroupsFeed({ enabled: true, includeSimilarity: true, isAdmin: false }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(mockFetchTagGroups).toHaveBeenCalledWith(undefined, true)
    expect(mockFetchPendingSuggestions).not.toHaveBeenCalled()
  })

  it('skips fetchPendingSuggestions when isAdmin is false, even with a token', async () => {
    const { result } = renderHook(
      () => useTagGroupsFeed({ enabled: true, includeSimilarity: false, isAdmin: false, token: 'tok-1' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.suggestions).toEqual([])
    expect(mockFetchPendingSuggestions).not.toHaveBeenCalled()
  })

  it('skips fetchPendingSuggestions when isAdmin is true but no token is given', async () => {
    const { result } = renderHook(
      () => useTagGroupsFeed({ enabled: true, includeSimilarity: false, isAdmin: true }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.suggestions).toEqual([])
    expect(mockFetchPendingSuggestions).not.toHaveBeenCalled()
  })

  it('calls fetchPendingSuggestions when both isAdmin and token are set', async () => {
    const { result } = renderHook(
      () => useTagGroupsFeed({ enabled: true, topicId: 't1', includeSimilarity: false, isAdmin: true, token: 'tok-1' }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(mockFetchPendingSuggestions).toHaveBeenCalledWith('tok-1')
    expect(result.current.data?.suggestions).toEqual([{ id: 'sg1' }])
  })
})
