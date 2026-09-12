'use client'
import useSWR from 'swr'
import { fetchAnalysesGraph, type GraphFilters, type GraphData } from '@/lib/api/graph'

interface UseGraphDataArgs {
  enabled: boolean
  filters: GraphFilters | null
  locale?: string
  /** SSR-seeded data for the very first render — see knowledge-graph.tsx's fingerprint-gated
   * wiring. Only ever passed while `filters` still matches what the server fetched; once the
   * visitor changes anything (topic, date range, source filters, …) the caller stops passing
   * this, and a normal SWR fetch runs for the new key. */
  fallbackData?: GraphData
}

/** `revalidateOnMount: false` while `fallbackData` is present is what actually skips the
 * redundant client-side duplicate of the SSR fetch `app/graph/page.tsx` just did — see
 * specs/021-ssr-public-pages FR-003. Once the visitor changes filters (fallbackData stops being
 * passed), this reverts to SWR's normal "always fetch a key with no cached data" default. */
export function useGraphData({ enabled, filters, locale, fallbackData }: UseGraphDataArgs) {
  const key = enabled && filters ? (['graph-data', filters, locale ?? 'en'] as const) : null
  const { data, isLoading } = useSWR<GraphData>(
    key,
    () => fetchAnalysesGraph(filters!, locale),
    { fallbackData, revalidateOnMount: fallbackData ? false : undefined },
  )
  return { data, isLoading }
}
