import { apiFetch } from './client'

export interface GraphNode {
  id: string
  label: string
  type: 'group' | 'article' | 'tag'
  color?: string
  groupName?: string
  articleCount?: number
  articleId?: string
}

export interface GraphEdge {
  source: string
  target: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}


export async function fetchGraph(topicId: string, locale?: string): Promise<GraphData> {
  const res = await apiFetch(`/graph?topic_id=${topicId}`, {}, locale)
  return res.json()
}

export interface GraphFilters {
  topic_id: string
  aggregator?: string[]
  published_after?: string
  published_before?: string
  scraped_after?: string
  scraped_before?: string
  original_source?: string[]
  tag?: string[]
  tag_group?: string[]
}

export async function fetchAnalysesGraph(
  filters: GraphFilters,
  locale?: string,
): Promise<GraphData> {
  const params = new URLSearchParams()
  params.set('topic_id', filters.topic_id)
  filters.aggregator?.forEach(a => params.append('aggregator', a))
  if (filters.published_after) params.set('published_after', filters.published_after)
  if (filters.published_before) params.set('published_before', filters.published_before)
  if (filters.scraped_after) params.set('scraped_after', filters.scraped_after)
  if (filters.scraped_before) params.set('scraped_before', filters.scraped_before)
  filters.original_source?.forEach(o => params.append('original_source', o))
  filters.tag?.forEach(t => params.append('tag', t))
  const res = await apiFetch(`/analyses/graph?${params.toString()}`, {}, locale)
  return res.json()
}

export async function fetchAnalysesGraphGroup<T = unknown>(
  groupName: string,
  filters?: Omit<GraphFilters, 'topic_id'> & { topic_id?: string },
  locale?: string,
): Promise<T[]> {
  const params = new URLSearchParams()
  if (filters?.topic_id) params.set('topic_id', filters.topic_id)
  filters?.aggregator?.forEach(a => params.append('aggregator', a))
  if (filters?.published_after) params.set('published_after', filters.published_after)
  if (filters?.published_before) params.set('published_before', filters.published_before)
  if (filters?.scraped_after) params.set('scraped_after', filters.scraped_after)
  if (filters?.scraped_before) params.set('scraped_before', filters.scraped_before)
  filters?.original_source?.forEach(o => params.append('original_source', o))
  filters?.tag?.forEach(t => params.append('tag', t))
  const qs = params.toString()
  const res = await apiFetch(
    `/analyses/graph/group/${encodeURIComponent(groupName)}${qs ? `?${qs}` : ''}`,
    {},
    locale,
  )
  return res.json()
}
