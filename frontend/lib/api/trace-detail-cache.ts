import { queryTraceById, type OtlpTraceResponse } from '@/lib/api/grafana'

// Plain module-level cache, not a React hook or SWR: every call site here is inside an
// imperative event handler (a table row's expand/click handler), not a component render,
// so there's no natural place to call useSWR. Mirrors authHeaders()'s own _tokenCache/
// _tokenPromise pattern elsewhere in this file's sibling module — same shape, same reason.
const cache = new Map<string, OtlpTraceResponse>()
const inFlight = new Map<string, Promise<OtlpTraceResponse>>()

/** Cache-aside wrapper around queryTraceById(), shared across every call site that fetches
 * a full trace by ID on demand — TracesTable's row-expand and its trace-ID waterfall link,
 * and LogsTable's "open trace" link (fix/profiler_imprv). Before this existed, each of
 * those was its own independent fetch with no way to know another one had already fetched
 * the same trace — same root cause as the CPU-profile double-fetch useProfileQuery fixes,
 * just triggered by two different user actions landing on the same trace instead of two
 * components mounting at once. */
export function fetchTraceDetail(traceId: string): Promise<OtlpTraceResponse> {
  const cached = cache.get(traceId)
  if (cached) return Promise.resolve(cached)
  let promise = inFlight.get(traceId)
  if (!promise) {
    promise = queryTraceById(traceId).then(data => {
      cache.set(traceId, data)
      inFlight.delete(traceId)
      return data
    }).catch(err => {
      inFlight.delete(traceId)
      throw err
    })
    inFlight.set(traceId, promise)
  }
  return promise
}

/** Test-only escape hatch. This module's cache is a page-load-lifetime singleton by design
 * (same as authHeaders()'s token cache) — but this codebase's own test suites routinely
 * reuse the same literal fixture trace ID (e.g. "trace001") across many unrelated `it()`
 * blocks, each mocking queryTraceById with its own different response. Without resetting
 * between tests, a later test would silently see an earlier test's cached response instead
 * of its own mock. Call this from a `beforeEach` in any test that touches fetchTraceDetail. */
export function __resetTraceDetailCacheForTests(): void {
  cache.clear()
  inFlight.clear()
}
