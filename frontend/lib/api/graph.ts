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

export async function fetchAnalysesGraph(
  days: number,
  topicId: string,
  locale?: string,
): Promise<GraphData> {
  const res = await apiFetch(
    `/analyses/graph?days=${days}&topic_id=${encodeURIComponent(topicId)}`,
    {},
    locale,
  )
  return res.json()
}

export async function fetchAnalysesGraphGroup<T = unknown>(
  groupName: string,
  locale?: string,
): Promise<T[]> {
  const res = await apiFetch(
    `/analyses/graph/group/${encodeURIComponent(groupName)}`,
    {},
    locale,
  )
  return res.json()
}
