import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useSpanPercentileThresholds } from '@/hooks/use-span-percentile-thresholds'
import type { OtlpSpan } from '@/lib/api/grafana'
import type { SpanNode } from '@/lib/otlp-utils'

const mockQueryTracesBatch = vi.fn()
vi.mock('@/lib/api/grafana', () => ({
  queryTracesBatch: (...args: any[]) => mockQueryTracesBatch(...args),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

function makeStageSpan(name: string): SpanNode {
  const span: OtlpSpan = {
    traceId: 'trace1',
    spanId: `${name}-span`,
    parentSpanId: 'root',
    name,
    startTimeUnixNano: '0',
    endTimeUnixNano: '1000000',
    attributes: [],
  }
  return { span, depth: 1 }
}

function tempoTraceWithDurations(durationsMs: number[]) {
  return {
    traceID: 't1',
    startTimeUnixNano: '0',
    spanSet: {
      matched: durationsMs.length,
      spans: durationsMs.map((ms, i) => ({
        spanID: `s${i}`,
        startTimeUnixNano: '0',
        durationNanos: String(ms * 1_000_000),
      })),
    },
  }
}

describe('useSpanPercentileThresholds', () => {
  it('does not fetch when closed', () => {
    const { result } = renderHook(() => useSpanPercentileThresholds(false, [makeStageSpan('a')]))
    expect(mockQueryTracesBatch).not.toHaveBeenCalled()
    expect(result.current.size).toBe(0)
  })

  it('does not fetch when there are no stage spans', () => {
    renderHook(() => useSpanPercentileThresholds(true, []))
    expect(mockQueryTracesBatch).not.toHaveBeenCalled()
  })

  it('dedupes repeated span names into a single query each', async () => {
    mockQueryTracesBatch.mockResolvedValue([{ traces: [] }])
    renderHook(() =>
      useSpanPercentileThresholds(true, [makeStageSpan('article.fetch'), makeStageSpan('article.fetch')])
    )
    await waitFor(() => expect(mockQueryTracesBatch).toHaveBeenCalledTimes(1))
    expect(mockQueryTracesBatch).toHaveBeenCalledWith([
      expect.objectContaining({ q: '{ name="article.fetch" }' }),
    ])
  })

  it('computes avg/count/durations only for a span name with >= 5 samples, excluding thinner ones', async () => {
    mockQueryTracesBatch.mockResolvedValue([
      { traces: [tempoTraceWithDurations([10, 20, 30, 40, 50])] }, // 5 samples -> included
      { traces: [tempoTraceWithDurations([10, 20])] },             // 2 samples -> excluded
    ])
    const { result } = renderHook(() =>
      useSpanPercentileThresholds(true, [makeStageSpan('well-sampled'), makeStageSpan('thin')])
    )

    await waitFor(() => expect(result.current.has('well-sampled')).toBe(true))
    expect(result.current.get('well-sampled')).toEqual({ avg: 30, count: 5, durations: [10, 20, 30, 40, 50] })
    expect(result.current.has('thin')).toBe(false)
  })
})
