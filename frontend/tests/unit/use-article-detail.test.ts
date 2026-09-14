import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useArticleDetail } from '@/hooks/use-article-detail'

const mockFetchArticleById = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: (...args: any[]) => mockFetchArticleById(...args),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useArticleDetail', () => {
  it('does not fetch and returns null detail while id is null/undefined (gated fetch)', () => {
    const { result } = renderHook(() => useArticleDetail(null), { wrapper: createSWRTestWrapper() })

    expect(result.current.detail).toBeNull()
    expect(mockFetchArticleById).not.toHaveBeenCalled()
  })

  it('fetches with locale undefined, while the SWR cache key still defaults it to "en"', async () => {
    // The cache key (line 15) defaults locale to 'en' so callers with/without an explicit
    // locale don't collide; the fetcher call itself (line 16) passes locale through as-is.
    mockFetchArticleById.mockResolvedValue({ id: 'a1', title: 'Title' })
    const { result } = renderHook(() => useArticleDetail('a1'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.detail).not.toBeNull())
    expect(mockFetchArticleById).toHaveBeenCalledWith('a1', undefined)
  })

  it('fetches with the given locale when passed', async () => {
    mockFetchArticleById.mockResolvedValue({ id: 'a2', title: '標題' })
    const { result } = renderHook(() => useArticleDetail('a2', 'zh-TW'), { wrapper: createSWRTestWrapper() })

    await waitFor(() => expect(result.current.detail).not.toBeNull())
    expect(mockFetchArticleById).toHaveBeenCalledWith('a2', 'zh-TW')
  })
})
