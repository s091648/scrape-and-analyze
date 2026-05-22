import { apiFetch } from './client'

export interface LlmProvider {
  id: string
  name: string
  model: string
  api_key_env: string
  priority: number
  is_active: boolean
  rpm: number | null
  tpm: number | null
  rpd: number | null
  usage_24h: number
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

export async function fetchLlmProviders(token?: string): Promise<LlmProvider[]> {
  const res = await throwOnError(
    await apiFetch('/llm-providers', { headers: authHeader(token) }),
  )
  return res.json()
}

export async function createLlmProvider(
  data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>,
  token?: string,
): Promise<LlmProvider> {
  const res = await throwOnError(
    await apiFetch('/llm-providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify(data),
    }),
  )
  return res.json()
}

export async function updateLlmProvider(
  id: string,
  data: Partial<LlmProvider>,
  token?: string,
): Promise<LlmProvider> {
  const res = await throwOnError(
    await apiFetch(`/llm-providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify(data),
    }),
  )
  return res.json()
}

export async function deleteLlmProvider(id: string, token?: string): Promise<void> {
  await throwOnError(
    await apiFetch(`/llm-providers/${id}`, { method: 'DELETE', headers: authHeader(token) }),
  )
}

export async function reorderLlmProviders(
  order: { id: string; priority: number }[],
  token?: string,
): Promise<LlmProvider[]> {
  const res = await throwOnError(
    await apiFetch('/llm-providers/reorder', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      body: JSON.stringify({ order }),
    }),
  )
  return res.json()
}
