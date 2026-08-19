'use client'
import { useMemo } from 'react'
import { useSearchParams } from 'next/navigation'

// Every setter below only ever needs to update the URL that the client-side fetch effects in
// articles-page-content.tsx already react to (via useSearchParams) — none of them need a fresh
// server render of app/articles/page.tsx (whose own SSR fetch result is only ever consumed once,
// at mount, per ArticlesPageContent's initialArticles/initialTotal props). Using next/navigation's
// router.push() here would still trigger that (wasted) server round-trip on every page/sort/filter/
// search change, since the route reads cookies()/searchParams and so can't be statically cached.
// The native History API updates the URL (and is picked up by useSearchParams, per Next.js docs)
// without going through the App Router's server-render pipeline at all.
function pushSearchParams(params: URLSearchParams) {
  window.history.pushState(null, '', `?${params.toString()}`)
}

export function usePagination() {
  const searchParams = useSearchParams()

  const page = parseInt(searchParams.get('page') || '1', 10)
  const sort = searchParams.get('sort') || 'scraped_at'
  const order = searchParams.get('order') || 'desc'
  // `sort`/`order` above always resolve to a value (defaulting to scraped_at/desc) so
  // SortSelect always has something to display — this is the only way to tell "the visitor
  // actually picked a sort" apart from "no sort param in the URL at all." Search (unlike
  // normal browsing) needs that distinction: applying `sort=scraped_at` unconditionally
  // would silently replace every un-sorted search's relevance ranking with a date sort by
  // default (see articles-page-content.tsx's search effect).
  const hasExplicitSort = searchParams.has('sort')
  const favoritesOnly = searchParams.get('favorites_only') === 'true'
  const searchQuery = searchParams.get('q') || ''

  // Memoized so array identity is stable between renders when URL hasn't changed
  const aggregators = useMemo(() => searchParams.getAll('aggregator'), [searchParams])
  const originalSources = useMemo(() => searchParams.getAll('original_source'), [searchParams])
  const tags = useMemo(() => searchParams.getAll('tag'), [searchParams])
  const tagGroups = useMemo(() => searchParams.getAll('tag_group'), [searchParams])
  const publishedAfter = searchParams.get('published_after') || ''
  const publishedBefore = searchParams.get('published_before') || ''
  const scrapedAfter = searchParams.get('scraped_after') || ''
  const scrapedBefore = searchParams.get('scraped_before') || ''

  function setPage(newPage: number) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('page', String(newPage))
    pushSearchParams(params)
  }

  function setSort(newSort: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('sort', newSort)
    params.set('page', '1')
    pushSearchParams(params)
  }

  function setOrder(newOrder: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('order', newOrder)
    params.set('page', '1')
    pushSearchParams(params)
  }

  // FR-010: applying a search sets `q`, matching the existing filter-param URL pattern;
  // clearing it (empty string) removes `q` entirely and returns to the normal
  // filtered/unfiltered list — same as every other setter here, page resets to 1.
  function setSearchQuery(query: string) {
    const params = new URLSearchParams(searchParams.toString())
    const trimmed = query.trim()
    if (trimmed) params.set('q', trimmed)
    else params.delete('q')
    params.set('page', '1')
    pushSearchParams(params)
  }

  function setFavoritesOnly(value: boolean) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set('favorites_only', 'true')
    else params.delete('favorites_only')
    params.set('page', '1')
    pushSearchParams(params)
  }

  function setFilters(updates: {
    aggregator?: string[]
    original_source?: string[]
    tag?: string[]
    tag_group?: string[]
    published_after?: string
    published_before?: string
    scraped_after?: string
    scraped_before?: string
  }) {
    // Built from the *current* params (not from scratch) so params this function doesn't know
    // about — `q` (active search), `favorites_only`, `article` — survive untouched. Rebuilding
    // from scratch here used to silently cancel an in-progress search and clear the
    // favorites-only toggle every time a filter was applied.
    const params = new URLSearchParams(searchParams.toString())
    params.set('page', '1')

    params.delete('aggregator')
    ;(updates.aggregator ?? aggregators).forEach(a => params.append('aggregator', a))

    params.delete('original_source')
    ;(updates.original_source ?? originalSources).forEach(o => params.append('original_source', o))

    params.delete('tag')
    ;(updates.tag ?? tags).forEach(t => params.append('tag', t))

    params.delete('tag_group')
    ;(updates.tag_group ?? tagGroups).forEach(g => params.append('tag_group', g))

    const pa = updates.published_after ?? publishedAfter
    const pb = updates.published_before ?? publishedBefore
    const sa = updates.scraped_after ?? scrapedAfter
    const sb = updates.scraped_before ?? scrapedBefore
    if (pa) params.set('published_after', pa)
    else params.delete('published_after')
    if (pb) params.set('published_before', pb)
    else params.delete('published_before')
    if (sa) params.set('scraped_after', sa)
    else params.delete('scraped_after')
    if (sb) params.set('scraped_before', sb)
    else params.delete('scraped_before')

    pushSearchParams(params)
  }

  const activeFilterCount = [
    aggregators.length > 0,
    originalSources.length > 0,
    tags.length > 0 || tagGroups.length > 0,
    !!(publishedAfter || publishedBefore),
    !!(scrapedAfter || scrapedBefore),
  ].filter(Boolean).length

  return {
    page, sort, order, hasExplicitSort, favoritesOnly, searchQuery,
    aggregators, originalSources, tags, tagGroups,
    publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    setPage, setSort, setOrder, setFilters, setFavoritesOnly, setSearchQuery,
    activeFilterCount,
  }
}
