'use client'
import useSWR from 'swr'
import { fetchArticles, type Article, type ArticleListParams } from '@/lib/api/articles'
import { searchArticles, type SearchParams } from '@/lib/api/search'

export interface ArticlesFeedResult {
  items: Article[]
  total: number
}

interface UseArticlesFeedArgs {
  enabled: boolean
  /** Non-empty → search mode (searchArticles); empty → plain listing (fetchArticles). Mirrors
   * articles-page-content.tsx's own two-effects-in-one-component split, now expressed as a single
   * key so SWR's own key-swap race protection replaces the old AbortController-based one (a
   * resolved response for a since-superseded key is simply never surfaced — SWR's standard
   * behavior, same guarantee the old code hand-rolled). */
  searchQuery: string
  listParams: ArticleListParams
  searchExtra: Omit<SearchParams, 'q'>
  locale?: string
  token?: string
  /** SSR-seeded first page for the current URL — see articles-page-content.tsx's fingerprint
   * gating for when this is (and stops being) passed. */
  fallbackData?: ArticlesFeedResult
}

const EMPTY_FEED: ArticlesFeedResult = { items: [], total: 0 }

/** `revalidateOnMount: false` while `fallbackData` is present skips the redundant client-side
 * duplicate of the SSR fetch `app/articles/page.tsx` just did (specs/021-ssr-public-pages
 * FR-003) — once the caller stops passing fallbackData (params changed), this reverts to SWR's
 * normal fetch-on-mount default. */
export function useArticlesFeed({
  enabled, searchQuery, listParams, searchExtra, locale, token, fallbackData,
}: UseArticlesFeedArgs) {
  const key = enabled
    ? searchQuery
      ? (['articles-feed', 'search', { q: searchQuery, ...searchExtra }, locale ?? 'en', token ?? null] as const)
      : (['articles-feed', 'list', listParams, locale ?? 'en', token ?? null] as const)
    : null

  const { data, isLoading } = useSWR<ArticlesFeedResult>(
    key,
    () => searchQuery
      ? searchArticles({ q: searchQuery, ...searchExtra }, locale, token)
      : fetchArticles(listParams, locale, token),
    { fallbackData, revalidateOnMount: fallbackData ? false : undefined },
  )

  return { data: data ?? EMPTY_FEED, isLoading: enabled ? isLoading : false }
}
