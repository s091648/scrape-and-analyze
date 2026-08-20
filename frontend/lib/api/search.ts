import { apiFetch } from './client'
import type { Article } from './articles'

export interface SearchParams {
  q: string
  topic_id?: string
  page?: number
  size?: number
  /** Drops non-exact-match candidates server-side before total/pagination are computed —
   * must go through the backend (023-article-search follow-up regression), not a
   * client-side per-page filter, or total/page count would disagree with what's shown. */
  exact_match_only?: boolean
  /** Same names/semantics as fetchArticles' own filter params (lib/api/articles.ts) —
   * narrows the candidate pool server-side before ranking/pagination (023-article-search
   * follow-up regression: these were previously silently ignored by /search entirely). */
  aggregator?: string[]
  original_source?: string[]
  tag?: string[]
  tag_group?: string[]
  published_after?: string
  published_before?: string
  scraped_after?: string
  scraped_before?: string
  /** Only send when the visitor explicitly picked a sort — omitting it keeps search
   * results in the backend's default order (RRF relevance, or newest-first for
   * exact_match_only). See articles-page-content.tsx's `hasExplicitSort`. */
  sort?: string
  order?: string
}

export interface AutocompleteSuggestion {
  term: string
  occurrence_count: number
}

export async function fetchAutocompleteSuggestions(
  prefix: string,
  topicId?: string,
  locale?: string,
  token?: string,
  signal?: AbortSignal,
): Promise<{ suggestions: AutocompleteSuggestion[] }> {
  const qs = new URLSearchParams()
  qs.set('prefix', prefix)
  if (topicId) qs.set('topic_id', topicId)

  const res = await apiFetch(
    `/search/autocomplete?${qs}`,
    { signal, ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}) },
    locale,
    { silent: true }, // a failed/aborted autocomplete lookup shouldn't toast — search itself is unaffected
  )
  return res.json()
}

export async function searchArticles(
  params: SearchParams,
  locale?: string,
  token?: string,
  signal?: AbortSignal,
): Promise<{ items: Article[]; total: number }> {
  const qs = new URLSearchParams()
  qs.set('q', params.q)
  if (params.topic_id) qs.set('topic_id', params.topic_id)
  if (params.page) qs.set('page', String(params.page))
  if (params.size) qs.set('size', String(params.size))
  if (params.exact_match_only) qs.set('exact_match_only', 'true')
  params.aggregator?.forEach(a => qs.append('aggregator', a))
  params.original_source?.forEach(o => qs.append('original_source', o))
  params.tag?.forEach(t => qs.append('tag', t))
  params.tag_group?.forEach(g => qs.append('tag_group', g))
  if (params.published_after) qs.set('published_after', params.published_after)
  if (params.published_before) qs.set('published_before', params.published_before)
  if (params.scraped_after) qs.set('scraped_after', params.scraped_after)
  if (params.scraped_before) qs.set('scraped_before', params.scraped_before)
  if (params.sort) qs.set('sort', params.sort)
  if (params.order) qs.set('order', params.order)

  const res = await apiFetch(
    `/search?${qs}`,
    { signal, ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}) },
    locale,
  )
  return res.json()
}
