import { Suspense } from 'react'
import ArticlesPageContent from './articles-page-content'
import { resolveSsrContext, fetchArticlesListSSR } from '@/lib/server/ssr-fetch'

type RawSearchParams = Record<string, string | string[] | undefined>

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function many(value: string | string[] | undefined): string[] {
  if (value === undefined) return []
  return Array.isArray(value) ? value : [value]
}

// Mirrors usePagination()/articles-page-content.tsx's fetchSearchParamsString — same params,
// same defaults — so the server-rendered fetch matches exactly what the client would otherwise
// have fetched on mount for this URL.
function buildArticlesQuery(searchParams: RawSearchParams): URLSearchParams {
  const qs = new URLSearchParams()
  const page = first(searchParams.page)
  if (page) qs.set('page', page)
  qs.set('sort', first(searchParams.sort) || 'scraped_at')
  qs.set('order', first(searchParams.order) || 'desc')
  many(searchParams.aggregator).forEach(a => qs.append('aggregator', a))
  many(searchParams.original_source).forEach(o => qs.append('original_source', o))
  many(searchParams.tag).forEach(t => qs.append('tag', t))
  many(searchParams.tag_group).forEach(g => qs.append('tag_group', g))
  const publishedAfter = first(searchParams.published_after)
  if (publishedAfter) qs.set('published_after', publishedAfter)
  const publishedBefore = first(searchParams.published_before)
  if (publishedBefore) qs.set('published_before', publishedBefore)
  const scrapedAfter = first(searchParams.scraped_after)
  if (scrapedAfter) qs.set('scraped_after', scrapedAfter)
  const scrapedBefore = first(searchParams.scraped_before)
  if (scrapedBefore) qs.set('scraped_before', scrapedBefore)
  return qs
}

export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<RawSearchParams>
}) {
  const resolvedSearchParams = await searchParams
  const context = await resolveSsrContext()
  // A shared/bookmarked `?topic=...` link overrides the visitor's cookie-stored topic for this
  // one render, matching TopicUrlSync's existing "URL wins" client-side behavior.
  const topicOverride = first(resolvedSearchParams.topic)
  const effectiveContext = topicOverride ? { ...context, topicId: topicOverride } : context

  const result = await fetchArticlesListSSR(effectiveContext, buildArticlesQuery(resolvedSearchParams))

  return (
    <Suspense fallback={<div />}>
      <ArticlesPageContent initialArticles={result?.items} initialTotal={result?.total} />
    </Suspense>
  )
}
