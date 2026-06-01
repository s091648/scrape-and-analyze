/**
 * Centralized observability constants for scrape-analyzer.
 *
 * TypeScript mirror of shared/enums/observability.py.
 * Keep in sync with the Python enum.
 */

// ── Service identity ─────────────────────────────────────────────────────────

export const SERVICE_NAME = 'scrape-analyzer' as const

// ── Metric names ─────────────────────────────────────────────────────────────

export const MetricName = {
  RUNS_TOTAL: 'scraper_runs_total',
  RUN_DURATION_SECONDS: 'scraper_run_duration_seconds',
  ARTICLES_FOUND_TOTAL: 'scraper_articles_found_total',
  ARTICLES_NEW_TOTAL: 'scraper_articles_new_total',
  ARTICLES_DUPLICATE_TOTAL: 'scraper_articles_duplicate_total',
  ERRORS_TOTAL: 'scraper_errors_total',
} as const

// ── Metric label keys & values ───────────────────────────────────────────────

export const MetricLabelKey = {
  SOURCE: 'source',
} as const

export const MetricSourceValue = {
  ARXIV: 'arxiv',
  RSS: 'rss',
  BLOG: 'blog',
} as const

// ── Loki labels (stream selectors — indexed) ────────────────────────────────

export const LokiLabel = {
  APP: 'app',
  ENV: 'env',
} as const

export const LokiAppValue = {
  SCRAPER: 'scraper',
} as const

export const LokiEnvValue = {
  PRODUCTION: 'production',
} as const

// ── Loki log fields (extracted via | json, NOT indexed) ─────────────────────

export const LogField = {
  LEVEL: 'level',
  EVENT: 'event',
  CORRELATION_ID: 'correlation_id',
} as const

export const LogLevel = {
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
} as const

// ── Span names ───────────────────────────────────────────────────────────────

export const SpanName = {
  SCRAPER_RUN: 'scraper.run',
  ARTICLE_SCRAPED_HANDLE: 'article.scraped.handle',
  ARTICLE_PROCESSED_HANDLE: 'article.processed.handle',
  TAG_NORMALIZATION_HANDLE: 'article.tag_normalization.handle',
  ANALYSIS_COMPLETED_HANDLE: 'article.analysis_completed.handle',
} as const

// ── Span attributes ──────────────────────────────────────────────────────────

export const SpanAttribute = {
  RUN_ID: 'run.id',
  CORRELATION_ID: 'run.correlation_id',
} as const

// ── Tempo TraceQL resource label ─────────────────────────────────────────────

export const TraceQLResource = {
  SERVICE_NAME: 'resource.service.name',
  DEPLOYMENT_ENVIRONMENT: 'resource.deployment.environment',
} as const

// ── Pre-built query helpers ──────────────────────────────────────────────────

/** Build a Loki stream selector: `{app="scraper"}` */
export function lokiStreamSelector(extra?: Record<string, string>): string {
  const pairs: string[] = [`${LokiLabel.APP}="${LokiAppValue.SCRAPER}"`]
  if (extra) {
    for (const [k, v] of Object.entries(extra)) pairs.push(`${k}="${v}"`)
  }
  return `{${pairs.join(', ')}}`
}

/** Build a TraceQL resource match: `{ resource.service.name = "scrape-analyzer" }` */
export function traceQLServiceMatch(): string {
  return `{ ${TraceQLResource.SERVICE_NAME} = "${SERVICE_NAME}" }`
}

/** Build a PromQL increase expression with optional by clause */
export function promqlIncrease(metric: string, range: string, byLabel?: string): string {
  const byClause = byLabel ? ` by (${byLabel})` : ''
  return `increase(${metric}[${range}])${byClause}`
}
