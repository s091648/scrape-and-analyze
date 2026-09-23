'use client'
import useSWR from 'swr'
import { queryProfile, type FlamebearerResponse } from '@/lib/api/grafana'

interface UseProfileQueryArgs {
  enabled: boolean
  /** unix seconds — see queryProfile's own doc comment for what start/end/service/spanId mean. */
  start: number
  end: number
  service?: 'backend' | 'scraper'
  spanId?: string
}

/** Shared SWR-cached CPU profile fetch — both FlameGraphDialog (the flame graph itself) and
 * RunWaterfallDialog (the always-visible CPU-utilization strip, spanId omitted for the whole
 * padded window) query the *same* (start, end, service, spanId) tuple for a trace's own
 * whole-window view, so this hook exists specifically so they share ONE SWR cache entry
 * instead of each independently fetching it — before this was extracted, opening the
 * waterfall (which fetches the whole-window profile for its overlay strip) followed by
 * clicking "View Profile" (same whole-window key, no spanId) fired the exact same query
 * twice, since only FlameGraphDialog's own fetch went through SWR — the overlay strip's own
 * plain fetch never populated the cache the second call could have reused.
 *
 * (start, end, service, spanId) is an already-resolved window into the past — unlike the
 * dashboard's live Operations/Logs/Traces batch queries, the same tuple always answers with
 * the same historical CPU samples, so revalidateOnFocus/revalidateIfStale are both off:
 * nothing to revalidate, a cache hit should be instant. */
export function useProfileQuery({ enabled, start, end, service, spanId }: UseProfileQueryArgs) {
  const key = enabled ? (['flame-profile', start, end, service ?? 'backend', spanId ?? null] as const) : null
  const { data, error, isLoading } = useSWR<FlamebearerResponse>(
    key,
    async () => {
      const res = await queryProfile({ start, end, service, spanId })
      // Only `not_configured` is a stable answer worth caching. Any other error (network blip,
      // Pyroscope 5xx) is thrown so SWR tracks it as `error` rather than cached data — with
      // revalidateIfStale off, a cached error would otherwise stick until a full page reload.
      // Nothing is cached for an errored key, so the next mount (reopening the dialog) refetches.
      const err = res && typeof res === 'object' && 'error' in res ? (res as { error: unknown }).error : undefined
      if (err !== undefined && err !== 'not_configured') throw new Error(String(err))
      return res
    },
    { revalidateOnFocus: false, revalidateIfStale: false, shouldRetryOnError: false },
  )
  // Consumers (FlameGraphDialog, the waterfall's CPU strip) only branch on `'error' in data`,
  // so surface a thrown fetch as the same `fetch_failed` shape they already handle.
  const shaped = error ? ({ error: 'fetch_failed' } as unknown as FlamebearerResponse) : data
  return { data: shaped, isLoading: enabled && isLoading }
}
