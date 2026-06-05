import { apiFetch } from './client'

export interface SourceEntry {
  value: string
  label: string
}

export interface SourceCategories {
  aggregator: SourceEntry[]
  scraper: SourceEntry[]
}

export async function fetchSourceCategories(): Promise<SourceCategories> {
  const res = await apiFetch('/source-categories')
  return res.json()
}
