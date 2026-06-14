import { apiFetch } from './client'

export interface RagEmbeddingProvider {
  id: string
  role: 'dense' | 'sparse'
  provider_type: 'endpoint' | 'local' | 'gemini'
  model: string | null
  endpoint_url: string | null
  api_key_env: string | null
  dimension: number
  is_active: boolean
  rpm: number | null
  tpm: number | null
  rpd: number | null
  created_at?: string | null
  updated_at?: string | null
}

function authHeader(token?: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function throwOnError(res: Response): Promise<Response> {
  if (!res.ok) {
    const err: any = new Error(`HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res
}

export async function fetchRagEmbeddingProviders(token?: string): Promise<RagEmbeddingProvider[]> {
  const res = await throwOnError(
    await apiFetch('/rag-embedding-providers', { headers: authHeader(token) }),
  )
  return res.json()
}

export async function createRagEmbeddingProvider(
  data: Omit<RagEmbeddingProvider, 'id' | 'created_at' | 'updated_at'>,
  token?: string,
): Promise<RagEmbeddingProvider> {
  const res = await throwOnError(
    await apiFetch('/rag-embedding-providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify(data),
    }),
  )
  return res.json()
}

export async function updateRagEmbeddingProvider(
  id: string,
  data: Partial<RagEmbeddingProvider>,
  token?: string,
): Promise<RagEmbeddingProvider> {
  const res = await throwOnError(
    await apiFetch(`/rag-embedding-providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify(data),
    }),
  )
  return res.json()
}

export async function deleteRagEmbeddingProvider(id: string, token?: string): Promise<void> {
  await throwOnError(
    await apiFetch(`/rag-embedding-providers/${id}`, { method: 'DELETE', headers: authHeader(token) }),
  )
}
