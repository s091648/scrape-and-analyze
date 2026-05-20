import { apiFetch } from './client'

export interface Article {
  id: string
  title: string
  source: string
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
  source?: string[]
  tag?: string[]
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
  params.source?.forEach(s => qs.append('source', s))
  params.tag?.forEach(t => qs.append('tag', t))
  if (params.published_after) qs.set('published_after', params.published_after)
  if (params.published_before) qs.set('published_before', params.published_before)
  if (params.scraped_after) qs.set('scraped_after', params.scraped_after)
  if (params.scraped_before) qs.set('scraped_before', params.scraped_before)
  const res = await apiFetch(`/articles?${qs}`, {}, locale)
  return res.json()
}

export async function fetchArticleById(id: string, locale?: string): Promise<ArticleDetail> {
  const res = await apiFetch(`/articles/${id}`, {}, locale)
  return res.json()
}

export async function fetchArticleFilterSources(locale?: string): Promise<string[]> {
  const res = await apiFetch('/articles/filters/sources', {}, locale)
  return res.json()
}

export async function fetchArticleFilterTags(locale?: string): Promise<string[]> {
  const res = await apiFetch('/articles/filters/tags', {}, locale)
  return res.json()
}
