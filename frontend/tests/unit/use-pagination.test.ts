import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useSearchParams } from 'next/navigation'

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(),
}))

// Setters now update the URL via the native History API (window.history.pushState) instead of
// next/navigation's router — see use-pagination.ts's pushSearchParams() comment for why (avoids
// triggering a redundant server render of app/articles/page.tsx on every page/sort/filter/search
// change). mockImplementation(() => {}) suppresses the real navigation side effect so tests don't
// leak URL state into each other; the pushed URL is read back from the spy's 3rd argument.
function setup(search = '') {
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams(search) as any)
  const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {})
  return { pushStateSpy }
}

function pushedUrl(pushStateSpy: ReturnType<typeof vi.spyOn>, callIndex = 0): string {
  return pushStateSpy.mock.calls[callIndex][2] as string
}

describe('usePagination', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.restoreAllMocks())

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
    const { pushStateSpy } = setup('page=1&sort=scraped_at')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setPage(2)
    expect(pushedUrl(pushStateSpy)).toContain('page=2')
  })

  it('setSort resets page to 1', async () => {
    const { pushStateSpy } = setup('page=3&sort=scraped_at')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setSort('published_at')
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('page=1')
    expect(calledWith).toContain('sort=published_at')
  })

  it('setFilters replaces specified params and clears unspecified ones when passed explicitly', async () => {
    const { pushStateSpy } = setup('original_source=old&tag=OldTag')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ original_source: ['rss'], tag: [] })
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('original_source=rss')
    expect(calledWith).not.toContain('OldTag')
  })

  it('setFilters preserves an in-progress search query (q) instead of clearing it', async () => {
    const { pushStateSpy } = setup('q=neural+networks&sort=scraped_at&order=desc')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ original_source: ['rss'] })
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('q=neural')
    expect(calledWith).toContain('original_source=rss')
  })

  it('setFilters preserves favorites_only instead of clearing it', async () => {
    const { pushStateSpy } = setup('favorites_only=true')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ tag: ['AI'] })
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('favorites_only=true')
  })

  it('setFilters clears a date param when the update explicitly unsets it', async () => {
    const { pushStateSpy } = setup('published_after=2026-01-01')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFilters({ published_after: '' })
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).not.toContain('published_after')
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
    const { pushStateSpy } = setup('page=3&order=desc')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setOrder('asc')
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('order=asc')
    expect(calledWith).toContain('page=1')
  })

  it('setFavoritesOnly(true) sets the param and resets page to 1', async () => {
    const { pushStateSpy } = setup('page=3')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFavoritesOnly(true)
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).toContain('favorites_only=true')
    expect(calledWith).toContain('page=1')
  })

  it('hasExplicitSort is false when the URL has no sort param', async () => {
    setup('')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.hasExplicitSort).toBe(false)
    expect(result.current.sort).toBe('scraped_at') // still resolves a default for display
  })

  it('hasExplicitSort is true once the URL has a sort param, even if it equals the default', async () => {
    setup('sort=scraped_at')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    expect(result.current.hasExplicitSort).toBe(true)
  })

  it('setFavoritesOnly(false) removes the param', async () => {
    const { pushStateSpy } = setup('favorites_only=true&page=2')
    const { usePagination } = await import('@/hooks/use-pagination')
    const { result } = renderHook(() => usePagination())
    result.current.setFavoritesOnly(false)
    const calledWith = pushedUrl(pushStateSpy)
    expect(calledWith).not.toContain('favorites_only')
    expect(calledWith).toContain('page=1')
  })
})
