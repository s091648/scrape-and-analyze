import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useSearchParams, useRouter } from 'next/navigation'

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
  useRouter: vi.fn(),
}))

function setup(search = '') {
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams(search) as any)
  const mockPush = vi.fn()
  vi.mocked(useRouter).mockReturnValue({ push: mockPush } as any)
  return { mockPush }
}

describe('usePagination', () => {
  beforeEach(() => vi.clearAllMocks())

  it('default values when URL has no params', async () => {
    setup('')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(1)
    expect(result.current.sort).toBe('scraped_at')
    expect(result.current.order).toBe('desc')
    expect(result.current.aggregators).toEqual([])
    expect(result.current.originalSources).toEqual([])
    expect(result.current.tags).toEqual([])
  })

  it('reads page from URL', async () => {
    setup('page=3')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(3)
  })

  it('reads multi-value original_source from URL', async () => {
    setup('original_source=rss&original_source=blog')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.originalSources).toEqual(['rss', 'blog'])
  })

  it('setPage pushes URL with updated page', async () => {
    const { mockPush } = setup('page=1&sort=scraped_at')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setPage(2)
    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining('page=2'))
  })

  it('setSort resets page to 1', async () => {
    const { mockPush } = setup('page=3&sort=scraped_at')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setSort('published_at')
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('page=1')
    expect(calledWith).toContain('sort=published_at')
  })

  it('setFilters replaces specified params and clears unspecified ones when passed explicitly', async () => {
    const { mockPush } = setup('original_source=old&tag=OldTag')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ original_source: ['rss'], tag: [] })
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('original_source=rss')
    expect(calledWith).not.toContain('OldTag')
  })

  it('activeFilterCount is 0 with no filters', async () => {
    setup('')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(0)
  })

  it('activeFilterCount increments per dimension', async () => {
    setup('original_source=rss')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(1)
  })

  it('activeFilterCount counts source + tag as 2', async () => {
    setup('original_source=rss&tag=AI')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(2)
  })

  it('favoritesOnly defaults to false when URL has no param', async () => {
    setup('')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.favoritesOnly).toBe(false)
  })

  it('favoritesOnly reads true from URL', async () => {
    setup('favorites_only=true')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.favoritesOnly).toBe(true)
  })

  it('favoritesOnly is false for any non-"true" value', async () => {
    setup('favorites_only=1')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.favoritesOnly).toBe(false)
  })

  it('setOrder pushes URL with updated order and resets page to 1', async () => {
    const { mockPush } = setup('page=3&order=desc')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setOrder('asc')
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('order=asc')
    expect(calledWith).toContain('page=1')
  })

  it('setFavoritesOnly(true) sets the param and resets page to 1', async () => {
    const { mockPush } = setup('page=3')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFavoritesOnly(true)
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('favorites_only=true')
    expect(calledWith).toContain('page=1')
  })

  it('setFavoritesOnly(false) removes the param', async () => {
    const { mockPush } = setup('favorites_only=true&page=2')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFavoritesOnly(false)
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).not.toContain('favorites_only')
    expect(calledWith).toContain('page=1')
  })
})
