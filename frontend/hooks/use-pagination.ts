'use client'
import { useMemo } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'

export function usePagination() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const page = parseInt(searchParams.get('page') || '1', 10)
  const sort = searchParams.get('sort') || 'scraped_at'
  const order = searchParams.get('order') || 'desc'
  const favoritesOnly = searchParams.get('favorites_only') === 'true'

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
    router.push(`?${params.toString()}`)
  }

  function setSort(newSort: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('sort', newSort)
    params.set('page', '1')
    router.push(`?${params.toString()}`)
  }

  function setFavoritesOnly(value: boolean) {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set('favorites_only', 'true')
    else params.delete('favorites_only')
    params.set('page', '1')
    router.push(`?${params.toString()}`)
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
    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('sort', sort)
    params.set('order', order)

    const newAggregators = updates.aggregator ?? aggregators
    newAggregators.forEach(a => params.append('aggregator', a))

    const newOriginalSources = updates.original_source ?? originalSources
    newOriginalSources.forEach(o => params.append('original_source', o))

    const newTags = updates.tag ?? tags
    newTags.forEach(t => params.append('tag', t))

    const newTagGroups = updates.tag_group ?? tagGroups
    newTagGroups.forEach(g => params.append('tag_group', g))

    const pa = updates.published_after ?? publishedAfter
    const pb = updates.published_before ?? publishedBefore
    const sa = updates.scraped_after ?? scrapedAfter
    const sb = updates.scraped_before ?? scrapedBefore
    if (pa) params.set('published_after', pa)
    if (pb) params.set('published_before', pb)
    if (sa) params.set('scraped_after', sa)
    if (sb) params.set('scraped_before', sb)

    router.push(`?${params.toString()}`)
  }

  const activeFilterCount = [
    aggregators.length > 0,
    originalSources.length > 0,
    tags.length > 0 || tagGroups.length > 0,
    !!(publishedAfter || publishedBefore),
    !!(scrapedAfter || scrapedBefore),
  ].filter(Boolean).length

  return {
    page, sort, order, favoritesOnly,
    aggregators, originalSources, tags, tagGroups,
    publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    setPage, setSort, setFilters, setFavoritesOnly,
    activeFilterCount,
  }
}
