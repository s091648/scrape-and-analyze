import { describe, it, expect } from 'vitest'
import {
  flattenSpans, getAttr, getResourceAttr, buildSpanTree,
  spanDurationMs, isErrorSpan, findArticlePipelineSpans,
  findWeeklyReportTopicSpans, findStageSpans, formatDuration,
  extractEnvironmentFromTrace, otlpIdToHex,
} from '@/lib/otlp-utils'
import type { OtlpTraceResponse, OtlpSpan } from '@/lib/api/grafana'

function makeSpan(overrides: Partial<OtlpSpan> = {}): OtlpSpan {
  return {
    traceId: 'trace1',
    spanId: 'span1',
    name: 'test.span',
    startTimeUnixNano: '1000000000',
    endTimeUnixNano:   '2000000000',
    attributes: [],
    ...overrides,
  }
}

function makeTrace(spans: OtlpSpan[], resourceAttrs: Array<{ key: string; value: { stringValue: string } }> = []): OtlpTraceResponse {
  return {
    batches: [{
      resource: { attributes: resourceAttrs },
      scopeSpans: [{ spans }],
    }],
  }
}

describe('flattenSpans', () => {
  it('returns all spans from all batches', () => {
    const s1 = makeSpan({ spanId: 's1' })
    const s2 = makeSpan({ spanId: 's2' })
    expect(flattenSpans(makeTrace([s1, s2]))).toEqual([s1, s2])
  })

  it('returns empty array for empty trace', () => {
    expect(flattenSpans(makeTrace([]))).toEqual([])
  })
})

describe('getAttr', () => {
  it('returns string value', () => {
    const span = makeSpan({ attributes: [{ key: 'foo', value: { stringValue: 'bar' } }] })
    expect(getAttr(span, 'foo')).toBe('bar')
  })

  it('returns parsed int value', () => {
    const span = makeSpan({ attributes: [{ key: 'count', value: { intValue: '42' } }] })
    expect(getAttr(span, 'count')).toBe(42)
  })

  it('returns bool value', () => {
    const span = makeSpan({ attributes: [{ key: 'ok', value: { boolValue: true } }] })
    expect(getAttr(span, 'ok')).toBe(true)
  })

  it('returns undefined for missing key', () => {
    expect(getAttr(makeSpan(), 'missing')).toBeUndefined()
  })
})

describe('getResourceAttr', () => {
  it('returns the string value of a resource attribute', () => {
    const trace = makeTrace([], [{ key: 'deployment.environment', value: { stringValue: 'production' } }])
    expect(getResourceAttr(trace, 'deployment.environment')).toBe('production')
  })

  it('returns undefined when attribute is absent', () => {
    expect(getResourceAttr(makeTrace([]), 'missing')).toBeUndefined()
  })
})

describe('spanDurationMs', () => {
  it('computes duration from nanoseconds', () => {
    const span = makeSpan({ startTimeUnixNano: '0', endTimeUnixNano: '1000000' })
    expect(spanDurationMs(span)).toBe(1)
  })

  it('handles large nanosecond values without overflow', () => {
    const span = makeSpan({
      startTimeUnixNano: '1748793600000000000',
      endTimeUnixNano:   '1748793645200000000',
    })
    expect(spanDurationMs(span)).toBeCloseTo(45200, 0)
  })
})

describe('isErrorSpan', () => {
  it('returns true for OTLP error code 2', () => {
    expect(isErrorSpan(makeSpan({ status: { code: 2 } }))).toBe(true)
  })

  it('returns true for Tempo string-enum code STATUS_CODE_ERROR', () => {
    // Tempo's OTLP-JSON export (protojson) serializes the enum by name, not by number.
    expect(isErrorSpan(makeSpan({ status: { code: 'STATUS_CODE_ERROR' } }))).toBe(true)
  })

  it('returns false for ok code 0', () => {
    expect(isErrorSpan(makeSpan({ status: { code: 0 } }))).toBe(false)
  })

  it('returns false when status is absent', () => {
    expect(isErrorSpan(makeSpan())).toBe(false)
  })
})

describe('buildSpanTree + findStageSpans', () => {
  it('groups children by parentSpanId', () => {
    const parent = makeSpan({ spanId: 'p1', name: 'article.pipeline' })
    const child1 = makeSpan({ spanId: 'c1', parentSpanId: 'p1', startTimeUnixNano: '2000', endTimeUnixNano: '3000' })
    const child2 = makeSpan({ spanId: 'c2', parentSpanId: 'p1', startTimeUnixNano: '1000', endTimeUnixNano: '2000' })
    const tree = buildSpanTree([parent, child1, child2])
    const result = findStageSpans(tree, 'p1')
    expect(result[0].span.spanId).toBe('c2')  // earlier start time first
    expect(result[1].span.spanId).toBe('c1')
  })

  it('returns empty array for span with no children', () => {
    const span = makeSpan({ spanId: 's1' })
    const tree = buildSpanTree([span])
    expect(findStageSpans(tree, 's1')).toEqual([])
  })
})

describe('findArticlePipelineSpans', () => {
  it('returns only article.pipeline spans sorted by start time', () => {
    const spans = [
      makeSpan({ spanId: 's1', name: 'scraper.run' }),
      makeSpan({ spanId: 's2', name: 'article.pipeline', startTimeUnixNano: '2000', endTimeUnixNano: '3000' }),
      makeSpan({ spanId: 's3', name: 'article.pipeline', startTimeUnixNano: '1000', endTimeUnixNano: '2000' }),
    ]
    const result = findArticlePipelineSpans(spans)
    expect(result).toHaveLength(2)
    expect(result[0].spanId).toBe('s3')
    expect(result[1].spanId).toBe('s2')
  })
})

describe('findWeeklyReportTopicSpans', () => {
  it('returns only weekly_report.topic spans sorted by start time', () => {
    const spans = [
      makeSpan({ spanId: 's1', name: 'scraper.run' }),
      makeSpan({ spanId: 's2', name: 'weekly_report.topic', startTimeUnixNano: '2000', endTimeUnixNano: '3000' }),
      makeSpan({ spanId: 's3', name: 'weekly_report.topic', startTimeUnixNano: '1000', endTimeUnixNano: '2000' }),
    ]
    const result = findWeeklyReportTopicSpans(spans)
    expect(result).toHaveLength(2)
    expect(result[0].spanId).toBe('s3')
    expect(result[1].spanId).toBe('s2')
  })
})

describe('extractEnvironmentFromTrace', () => {
  it('reads deployment.environment directly when present', () => {
    const trace = makeTrace([], [{ key: 'deployment.environment', value: { stringValue: 'production' } }])
    expect(extractEnvironmentFromTrace(trace)).toBe('production')
  })

  it('falls back to the resource.-prefixed attribute name', () => {
    const trace = makeTrace([], [{ key: 'resource.deployment.environment', value: { stringValue: 'staging' } }])
    expect(extractEnvironmentFromTrace(trace)).toBe('staging')
  })
})

describe('otlpIdToHex', () => {
  it('returns empty/falsy id unchanged', () => {
    expect(otlpIdToHex('')).toBe('')
  })

  it('lowercases an already-hex id', () => {
    expect(otlpIdToHex('ABCDEF12')).toBe('abcdef12')
  })

  it('decodes a base64-encoded id to hex', () => {
    // atob('q80=') decodes to the two bytes 0xAB, 0xCD
    expect(otlpIdToHex('q80=')).toBe('abcd')
  })

  it('returns the original id unchanged when it is neither valid hex nor decodable base64', () => {
    expect(otlpIdToHex('not-valid-!!!')).toBe('not-valid-!!!')
  })
})

describe('formatDuration', () => {
  it('formats sub-second as ms', () => {
    expect(formatDuration(500)).toBe('500 ms')
  })

  it('formats seconds', () => {
    expect(formatDuration(12300)).toBe('12.3 s')
  })

  it('formats minutes', () => {
    expect(formatDuration(90000)).toBe('1.5 m')
  })
})