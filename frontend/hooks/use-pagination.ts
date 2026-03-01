'use client'
import { useMemo } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'

export function usePagination() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const page = parseInt(searchParams.get('page') || '1', 10)
  const sort = searchParams.get('sort') || 'scraped_at'
  const order = searchParams.get('order') || 'desc'

  // Memoized so array identity is stable between renders when URL hasn't changed
  const sources = useMemo(() => searchParams.getAll('source'), [searchParams])
  const tags = useMemo(() => searchParams.getAll('tag'), [searchParams])
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

  function setFilters(updates: {
    source?: string[]
    tag?: string[]
    published_after?: string
    published_before?: string
    scraped_after?: string
    scraped_before?: string
  }) {
    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('sort', sort)
    params.set('order', order)

    const newSources = updates.source ?? sources
    newSources.forEach(s => params.append('source', s))

    const newTags = updates.tag ?? tags
    newTags.forEach(t => params.append('tag', t))

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
    sources.length > 0,
    tags.length > 0,
    !!(publishedAfter || publishedBefore),
    !!(scrapedAfter || scrapedBefore),
  ].filter(Boolean).length

  return {
    page, sort, order,
    sources, tags, publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    setPage, setSort, setFilters,
    activeFilterCount,
  }
}
