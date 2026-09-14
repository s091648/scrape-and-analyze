import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { createSWRTestWrapper } from '@/tests/test-utils/swr'
import { useArticlesFeed } from '@/hooks/use-articles-feed'

const mockFetchArticles = vi.fn()
const mockSearchArticles = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticles: (...args: any[]) => mockFetchArticles(...args),
}))
vi.mock('@/lib/api/search', () => ({
  searchArticles: (...args: any[]) => mockSearchArticles(...args),
}))

const listParams = { page: 1 } as any

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useArticlesFeed', () => {
  it('does not fetch and reports isLoading=false when disabled, regardless of searchQuery', () => {
    const { result } = renderHook(
      () => useArticlesFeed({ enabled: false, searchQuery: '', listParams, searchExtra: {} }),
      { wrapper: createSWRTestWrapper() },
    )

    expect(result.current.isLoading).toBe(false)
    expect(result.current.data).toEqual({ items: [], total: 0 })
    expect(mockFetchArticles).not.toHaveBeenCalled()
    expect(mockSearchArticles).not.toHaveBeenCalled()
  })

  it('search mode: defaults locale to "en" and token to null when neither is passed', async () => {
    mockSearchArticles.mockResolvedValue({ items: [{ id: '1' }], total: 1 })
    const { result } = renderHook(
      () => useArticlesFeed({ enabled: true, searchQuery: 'llm', listParams, searchExtra: {} }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data.total).toBe(1))
    expect(mockSearchArticles).toHaveBeenCalledWith({ q: 'llm' }, undefined, undefined)
    expect(mockFetchArticles).not.toHaveBeenCalled()
  })

  it('list mode: defaults locale to "en" and token to null when neither is passed', async () => {
    mockFetchArticles.mockResolvedValue({ items: [{ id: '2' }], total: 1 })
    const { result } = renderHook(
      () => useArticlesFeed({ enabled: true, searchQuery: '', listParams, searchExtra: {} }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(result.current.data.total).toBe(1))
    expect(mockFetchArticles).toHaveBeenCalledWith(listParams, undefined, undefined)
    expect(mockSearchArticles).not.toHaveBeenCalled()
  })

  it('list mode: passes the given locale and token through', async () => {
    mockFetchArticles.mockResolvedValue({ items: [], total: 0 })
    renderHook(
      () => useArticlesFeed({
        enabled: true, searchQuery: '', listParams, searchExtra: {}, locale: 'zh-TW', token: 'tok-1',
      }),
      { wrapper: createSWRTestWrapper() },
    )

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalled())
    expect(mockFetchArticles).toHaveBeenCalledWith(listParams, 'zh-TW', 'tok-1')
  })
})
