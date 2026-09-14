'use client'
import useSWR from 'swr'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'

/** Shared cache for article detail lookups — replaces the old module-level LRU cache in
 * lib/api/articles.ts. Every call site (article-card.tsx's dialog, knowledge-graph.tsx's dialog)
 * uses this same hook, so opening the same article from either place hits the same SWR cache
 * entry keyed by (id, locale) instead of each call site (or the old single shared LRU) managing
 * its own copy.
 *
 * `id` is nullable so a caller can declaratively gate the fetch on "is the dialog/panel that
 * needs this actually open" (pass `null`/`undefined` while closed) rather than issuing a request
 * that's immediately thrown away. */
export function useArticleDetail(id: string | null | undefined, locale?: string) {
  const key = id ? (['article-detail', id, locale ?? 'en'] as const) : null
  const { data, isLoading, error } = useSWR<ArticleDetail>(key, () => fetchArticleById(id!, locale))
  return { detail: data ?? null, loading: isLoading, error }
}
