import { apiFetch } from './client'
import { LRUCache } from '@/lib/cache/lru-cache'

export interface Article {
  id: string
  title: string
  source: string
  via_source?: string | null
  original_source?: string | null
  content: string
  published_at: string | null
  scraped_at: string | null
  url: string
  translated_title?: string | null
  translated_content?: string | null
  has_vectors?: boolean
  metrics?: Record<string, number>
  view_count?: number
  is_favorited?: boolean
  /** Only ever set by /search (RRF hybrid search) — undefined for the normal listing
   * endpoint, where "exact match" isn't a meaningful concept. */
  exact_match?: boolean
}

export interface TagGroup {
  group_name: string
  display_name: string
  color: string
  tags: string[]
}

export interface ArticleDetail extends Article {
  tags: string[]
  tag_groups: TagGroup[]
  pain_points: string | null
  insights: string | null
  innovations: string | null
  model_used: string | null
  translated_title?: string | null
  translated_content?: string | null
}

export interface ArticleListParams {
  page?: number
  size?: number
  topic_id?: string
  aggregator?: string[]
  original_source?: string[]
  tag?: string[]
  tag_id?: string[]
  tag_group?: string[]
  published_after?: string
  published_before?: string
  scraped_after?: string
  scraped_before?: string
  sort?: string
  order?: string
}

export async function fetchArticles(
  params: ArticleListParams,
  locale?: string,
  token?: string,
): Promise<{ items: Article[]; total: number }> {
  const qs = new URLSearchParams()
  if (params.page) qs.set('page', String(params.page))
  if (params.size) qs.set('size', String(params.size))
  if (params.topic_id) qs.set('topic_id', params.topic_id)
  if (params.sort) qs.set('sort', params.sort)
  if (params.order) qs.set('order', params.order)
  params.aggregator?.forEach(a => qs.append('aggregator', a))
  params.original_source?.forEach(o => qs.append('original_source', o))
  params.tag?.forEach(t => qs.append('tag', t))
  params.tag_id?.forEach(id => qs.append('tag_id', id))
  params.tag_group?.forEach(g => qs.append('tag_group', g))
  if (params.published_after) qs.set('published_after', params.published_after)
  if (params.published_before) qs.set('published_before', params.published_before)
  if (params.scraped_after) qs.set('scraped_after', params.scraped_after)
  if (params.scraped_before) qs.set('scraped_before', params.scraped_before)
  // Sent when logged in so the backend can annotate each article with is_favorited —
  // without it, get_optional_user_id() always resolves to None (GET /articles is public).
  const res = await apiFetch(`/articles?${qs}`, token ? { headers: { Authorization: `Bearer ${token}` } } : {}, locale)
  return res.json()
}

// Per-session (in-memory, cleared on reload — no sessionStorage/localStorage) cache of article
// detail responses, so re-opening a dialog for a recently viewed article skips the network
// round-trip. Capacity 10, evicted LRU. Keyed by locale+id since translated_title/content differ
// per locale. view_count/metrics are cached along with everything else (unlike the backend's own
// cache, which deliberately excludes them for freshness — see backend/routers/articles.py) since
// staleness here is bounded to one browser tab's session and a few minutes, not worth a second
// endpoint just to keep them live.
const ARTICLE_DETAIL_CACHE_CAPACITY = 10
const articleDetailCache = new LRUCache<string, ArticleDetail>(ARTICLE_DETAIL_CACHE_CAPACITY)

export async function fetchArticleById(id: string, locale?: string, silent?: boolean): Promise<ArticleDetail> {
  const cacheKey = `${locale ?? 'en'}:${id}`
  const cached = articleDetailCache.get(cacheKey)
  if (cached) return cached

  const res = await apiFetch(`/articles/${id}`, {}, locale, { silent })
  if (!res.ok) throw new Error(`${res.status}`)
  const data: ArticleDetail = await res.json()
  articleDetailCache.set(cacheKey, data)
  return data
}

/** Test-only escape hatch — the cache above is a module singleton, so tests that reuse the
 * same (id, locale) across cases need a way to reset it between runs. */
export function __resetArticleDetailCacheForTests(): void {
  articleDetailCache.clear()
}

export async function fetchArticleFilterSources(locale?: string): Promise<string[]> {
  const res = await apiFetch('/articles/filters/sources', {}, locale)
  return res.json()
}

export async function fetchArticleFilterOriginalSources(topicId?: string, locale?: string): Promise<string[]> {
  const qs = topicId ? `?topic_id=${topicId}` : ''
  const res = await apiFetch(`/articles/filters/original-sources${qs}`, {}, locale)
  return res.json()
}

export async function fetchArticleFilterTags(locale?: string): Promise<string[]> {
  const res = await apiFetch('/articles/filters/tags', {}, locale)
  return res.json()
}

// Per-session, unbounded (article ids are tiny strings — no LRU/capacity needed the way the
// content cache above needs one) record of "already sent a view POST for this article", keyed by
// id alone (not locale — viewing the same article in a different language still counts as having
// viewed it, so this is intentionally coarser than articleDetailCache's key). The backend already
// deduplicates repeat views per-IP over 24h (see backend/routers/articles.py's `viewed:{ip}:{id}`
// Redis key), so this is purely an optimization to skip the network round-trip for the common
// case of reopening the same article within one tab session — it is never the source of truth for
// whether a view counts.
const viewedThisSession = new Set<string>()

export function recordArticleView(id: string): void {
  if (viewedThisSession.has(id)) return
  viewedThisSession.add(id)
  apiFetch(`/articles/${id}/view`, { method: 'POST' }, undefined, { silent: true }).catch(() => {
    viewedThisSession.delete(id) // let a failed request retry on the next open
  })
}

/** Test-only escape hatch, mirrors __resetArticleDetailCacheForTests. */
export function __resetViewedThisSessionForTests(): void {
  viewedThisSession.clear()
}
