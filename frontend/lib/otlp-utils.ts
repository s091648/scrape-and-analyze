import type { OtlpTraceResponse, OtlpSpan, OtlpAttribute, OtlpAttributeValue, OtlpResourceSpans, TempoTrace } from './api/grafana'
import { SpanName } from './observability-constants'

function getBatches(trace: OtlpTraceResponse): OtlpResourceSpans[] {
  // Backend normalises resourceSpans → batches; access batches directly.
  // Fallback handles any raw Tempo response that bypasses the backend proxy.
  return (trace.batches ?? (trace as unknown as { resourceSpans?: OtlpResourceSpans[] }).resourceSpans ?? [])
}

export function flattenSpans(trace: OtlpTraceResponse): OtlpSpan[] {
  return getBatches(trace).flatMap(b => b.scopeSpans.flatMap(s => s.spans))
}

export function getAttr(span: OtlpSpan, key: string): string | boolean | number | undefined {
  // Tempo omits the `attributes` field entirely for a span with none (rather
  // than returning an empty array), despite OtlpSpan typing it as required.
  const attr = span.attributes?.find(a => a.key === key)
  if (!attr) return undefined
  return resolveAttrValue(attr.value)
}

export function getResourceAttr(trace: OtlpTraceResponse, key: string): string | undefined {
  for (const batch of getBatches(trace)) {
    const attr = batch.resource.attributes?.find(a => a.key === key)
    if (attr?.value?.stringValue !== undefined) return attr.value.stringValue
  }
  return undefined
}

export function resolveAttrValue(v: OtlpAttributeValue): string | boolean | number | undefined {
  if (v.boolValue !== undefined) return v.boolValue
  if (v.intValue !== undefined) return parseInt(v.intValue, 10)
  if (v.doubleValue !== undefined) return v.doubleValue
  return v.stringValue
}

export function buildSpanTree(spans: OtlpSpan[]): Map<string, OtlpSpan[]> {
  const tree = new Map<string, OtlpSpan[]>()
  for (const span of spans) {
    const parentId = span.parentSpanId ?? ''
    if (!tree.has(parentId)) tree.set(parentId, [])
    tree.get(parentId)!.push(span)
  }
  return tree
}

export function spanDurationMs(span: OtlpSpan): number {
  const start = BigInt(span.startTimeUnixNano)
  const end = BigInt(span.endTimeUnixNano)
  return Number(end - start) / 1_000_000
}

export function isErrorSpan(span: OtlpSpan): boolean {
  // Tempo's OTLP-JSON export serializes the enum as its name (protojson default),
  // e.g. "STATUS_CODE_ERROR", not the numeric 2 — accept both forms.
  const code = span.status?.code
  return code === 2 || code === 'STATUS_CODE_ERROR'
}

export type ArticleRowStatus = 'ok' | 'partial' | 'failed'

/**
 * Roll a pipeline span + its stage spans into a tri-state status:
 *  - 'failed'  : the pipeline couldn't even scrape/save the article
 *                (article.scraped.handle errored, or article.pipeline itself did).
 *  - 'partial' : the article was scraped, but a later stage failed
 *                (analysis / tag normalization / translation / RAG ingestion).
 *                Only our own `article.*` stage spans count — a recovered
 *                transient error on an auto-instrumented HTTP/DB child span
 *                (e.g. an LLM call that timed out then retried past it, which
 *                Tempo shows as `exception.escaped=false`) does NOT flip this.
 *  - 'ok'      : no stage failure.
 */
export function articleRowStatus(pipelineSpan: OtlpSpan, stageSpans: SpanNode[]): ArticleRowStatus {
  const scraped = stageSpans.find(n => n.span.name === SpanName.ARTICLE_SCRAPED_HANDLE)
  if ((scraped && isErrorSpan(scraped.span)) || isErrorSpan(pipelineSpan)) return 'failed'
  const stageFailed = stageSpans.some(
    n => n.span.name.startsWith('article.') && isErrorSpan(n.span),
  )
  return stageFailed ? 'partial' : 'ok'
}

export function findArticlePipelineSpans(spans: OtlpSpan[]): OtlpSpan[] {
  return spans
    .filter(s => s.name === SpanName.ARTICLE_PIPELINE)
    .sort((a, b) => Number(BigInt(a.startTimeUnixNano) - BigInt(b.startTimeUnixNano)))
}

export function findWeeklyReportTopicSpans(spans: OtlpSpan[]): OtlpSpan[] {
  return spans
    .filter(s => s.name === SpanName.WEEKLY_REPORT_TOPIC)
    .sort((a, b) => Number(BigInt(a.startTimeUnixNano) - BigInt(b.startTimeUnixNano)))
}

export interface SpanNode {
  span: OtlpSpan
  depth: number
}

export function findStageSpans(tree: Map<string, OtlpSpan[]>, pipelineSpanId: string): SpanNode[] {
  const result: SpanNode[] = []
  const queue: Array<{ parentId: string; depth: number }> = [{ parentId: pipelineSpanId, depth: 0 }]
  while (queue.length > 0) {
    const { parentId, depth } = queue.shift()!
    const children = tree.get(parentId) ?? []
    for (const child of children) {
      result.push({ span: child, depth })
      queue.push({ parentId: child.spanId, depth: depth + 1 })
    }
  }
  return result.sort(
    (a, b) => Number(BigInt(a.span.startTimeUnixNano) - BigInt(b.span.startTimeUnixNano))
  )
}

/**
 * Reads deployment.environment off a Tempo /api/search result trace (the lightweight
 * TempoTrace shape — spanSet/spanSets, not a full span tree). Requires the TraceQL query to
 * have used `| select(resource.deployment.environment)` for Tempo to populate this attribute
 * on the search result at all — see traceQLServiceMatch() in observability-constants.ts.
 */
export function extractTraceSearchEnvironment(trace: TempoTrace): string | undefined {
  const spanSet = trace.spanSet ?? trace.spanSets?.[0]
  const attrs = spanSet?.attributes ?? spanSet?.spans?.[0]?.attributes ?? []
  const attr = attrs.find(
    a => a.key === 'deployment.environment' || a.key === 'resource.deployment.environment'
  )
  return attr?.value?.stringValue
}

export function extractEnvironmentFromTrace(trace: OtlpTraceResponse): string | undefined {
  // Tempo may prefix resource attributes with 'resource.' or not — check both.
  return (
    getResourceAttr(trace, 'deployment.environment') ??
    getResourceAttr(trace, 'resource.deployment.environment')
  )
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)} ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60000).toFixed(1)} m`
}

/**
 * Normalise an OTLP trace/span ID to lowercase hex.
 * Tempo's OTLP HTTP response encodes binary IDs as base64 (proto JSON encoding).
 * Python structlog emits them as hex (via `format(id, "032x")`).
 * This function detects whichever format is used and always returns hex,
 * so Loki label-filter queries and span highlight comparisons work correctly.
 */
export function otlpIdToHex(id: string): string {
  if (!id) return id
  // Already lowercase or uppercase hex — return normalised
  if (/^[0-9a-fA-F]+$/.test(id)) return id.toLowerCase()
  // Base64 — convert binary to hex
  try {
    const binary = atob(id)
    return Array.from(binary, c => c.charCodeAt(0).toString(16).padStart(2, '0')).join('')
  } catch {
    return id
  }
}