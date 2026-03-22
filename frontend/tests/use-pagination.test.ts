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
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(1)
    expect(result.current.sort).toBe('scraped_at')
    expect(result.current.order).toBe('desc')
    expect(result.current.sources).toEqual([])
    expect(result.current.tags).toEqual([])
  })

  it('reads page from URL', async () => {
    setup('page=3')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(3)
  })

  it('reads multi-value sources from URL', async () => {
    setup('source=rss&source=blog')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.sources).toEqual(['rss', 'blog'])
  })

  it('setPage pushes URL with updated page', async () => {
    const { mockPush } = setup('page=1&sort=scraped_at')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setPage(2)
    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining('page=2'))
  })

  it('setSort resets page to 1', async () => {
    const { mockPush } = setup('page=3&sort=scraped_at')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setSort('published_at')
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('page=1')
    expect(calledWith).toContain('sort=published_at')
  })

  it('setFilters replaces specified params and clears unspecified ones when passed explicitly', async () => {
    const { mockPush } = setup('source=old&tag=OldTag')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ source: ['rss'], tag: [] })
    const calledWith: string = mockPush.mock.calls[0][0]
    expect(calledWith).toContain('source=rss')
    expect(calledWith).not.toContain('OldTag')
  })

  it('activeFilterCount is 0 with no filters', async () => {
    setup('')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(0)
  })

  it('activeFilterCount increments per dimension', async () => {
    setup('source=rss')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(1)
  })

  it('activeFilterCount counts source + tag as 2', async () => {
    setup('source=rss&tag=AI')
    const { usePagination } = await import('../hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.activeFilterCount).toBe(2)
  })
})
