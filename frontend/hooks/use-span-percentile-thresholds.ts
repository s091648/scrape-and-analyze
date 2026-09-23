'use client'
import { useEffect, useState } from 'react'
import { queryTracesBatch } from '@/lib/api/grafana'
import type { SpanNode } from '@/lib/otlp-utils'
import type { SpanPercentileThresholds } from '@/components/features/monitoring/stage-card'

function computeThresholds(durations: number[]): SpanPercentileThresholds {
  const avg = durations.reduce((sum, d) => sum + d, 0) / durations.length
  return { avg, count: durations.length, durations }
}

/** Per-span-name duration percentile thresholds over the trailing 7 days, keyed by span
 * name — used by StageCard to color a stage's duration relative to its own historical
 * spread. Extracted out of ArticleWorkflowDialog and WeeklyReportTopicDialog
 * (fix/profiler_imprv), which had this exact query+aggregation logic duplicated verbatim:
 * same 7-day query window, same `{ name="..." }` TraceQL shape, same >=5-sample floor before
 * a span name gets a threshold at all. Not SWR-cached like useProfileQuery/fetchTraceDetail
 * — `now` is recomputed fresh on every call (this is a rolling window, not a fixed past
 * range), so a cache key here would rarely hit anyway without deliberately time-bucketing
 * `now`, which isn't worth it for a query this cheap (one batch call, run once per dialog
 * open). */
export function useSpanPercentileThresholds(open: boolean, stageSpans: SpanNode[]) {
  const [percentileMap, setPercentileMap] = useState<Map<string, SpanPercentileThresholds>>(new Map())

  useEffect(() => {
    if (!open || stageSpans.length === 0) return
    let cancelled = false
    const spanNames = [...new Set(stageSpans.map(n => n.span.name))]
    const now = Math.floor(Date.now() / 1000)
    const queries = spanNames.map(name => ({
      q: `{ name="${name}" }`,
      start: now - 7 * 86400,
      end: now,
      limit: 200,
    }))
    queryTracesBatch(queries).then(responses => {
      if (cancelled) return
      const map = new Map<string, SpanPercentileThresholds>()
      responses.forEach((res, i) => {
        const durations: number[] = []
        for (const trace of res.traces ?? []) {
          const spanSets = trace.spanSets ?? (trace.spanSet ? [trace.spanSet] : [])
          for (const ss of spanSets) {
            for (const s of ss.spans ?? []) {
              if (s.durationNanos) durations.push(Number(BigInt(s.durationNanos) / 1_000_000n))
            }
          }
        }
        if (durations.length >= 5) map.set(spanNames[i], computeThresholds(durations))
      })
      setPercentileMap(map)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [open, stageSpans])

  return percentileMap
}
