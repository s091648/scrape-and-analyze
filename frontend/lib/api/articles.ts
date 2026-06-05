import { apiFetch } from './client'

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
  const res = await apiFetch(`/articles?${qs}`, {}, locale)
  return res.json()
}

export async function fetchArticleById(id: string, locale?: string): Promise<ArticleDetail> {
  const res = await apiFetch(`/articles/${id}`, {}, locale)
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
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
