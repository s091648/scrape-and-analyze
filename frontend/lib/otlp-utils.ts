import type { OtlpTraceResponse, OtlpSpan, OtlpAttribute, OtlpAttributeValue, OtlpResourceSpans } from './api/grafana'
import { SpanName } from './observability-constants'

export function flattenSpans(trace: OtlpTraceResponse): OtlpSpan[] {
  return trace.batches.flatMap(b => b.scopeSpans.flatMap(s => s.spans))
}

export function getAttr(span: OtlpSpan, key: string): string | boolean | number | undefined {
  const attr = span.attributes.find(a => a.key === key)
  if (!attr) return undefined
  return resolveAttrValue(attr.value)
}

export function getResourceAttr(trace: OtlpTraceResponse, key: string): string | undefined {
  for (const batch of trace.batches) {
    const attr = batch.resource.attributes.find(a => a.key === key)
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
  return (span.status?.code ?? 0) === 2  // OTLP StatusCode.ERROR = 2
}

export function findArticlePipelineSpans(spans: OtlpSpan[]): OtlpSpan[] {
  return spans
    .filter(s => s.name === SpanName.ARTICLE_PIPELINE)
    .sort((a, b) => Number(BigInt(a.startTimeUnixNano) - BigInt(b.startTimeUnixNano)))
}

export function findStageSpans(tree: Map<string, OtlpSpan[]>, pipelineSpanId: string): OtlpSpan[] {
  return (tree.get(pipelineSpanId) ?? []).sort(
    (a, b) => Number(BigInt(a.startTimeUnixNano) - BigInt(b.startTimeUnixNano))
  )
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