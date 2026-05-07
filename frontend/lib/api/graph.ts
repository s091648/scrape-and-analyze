import { apiFetch } from './client'

export interface GraphData {
  nodes: { id: string; label: string; [key: string]: unknown }[]
  edges: { source: string; target: string; [key: string]: unknown }[]
}

export async function fetchGraph(topicId: string, locale?: string): Promise<GraphData> {
  const res = await apiFetch(`/graph?topic_id=${topicId}`, {}, locale)
  return res.json()
}
