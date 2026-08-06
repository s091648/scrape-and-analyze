/**
 * Centralized observability constants for scrape-analyzer.
 *
 * TypeScript mirror of shared/enums/observability.py.
 * Keep in sync with the Python enum.
 */

// ── Service identity ─────────────────────────────────────────────────────────

export const SERVICE_NAME = 'scrape-analyzer' as const
export const SERVICE_NAME_BACKEND = 'scrape-analyzer-backend' as const

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
  DEPLOYMENT_ENVIRONMENT: 'deployment_environment',
} as const

export const MetricEnvValue = {
  LOCAL: 'local',
  PRODUCTION: 'production',
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
  DETECTED_LEVEL: 'detected_level',
} as const

export const LokiAppValue = {
  SCRAPER: 'scraper',
  BACKEND: 'backend',
} as const

export const LokiEnvValue = {
  PRODUCTION: 'production',
} as const

// ── Loki log fields (extracted via | json, NOT indexed) ─────────────────────

export const LogField = {
  LEVEL: 'level',
  EVENT: 'event',
  CORRELATION_ID: 'correlation_id',
  TOPIC_ID: 'topic_id',
} as const

export const LogLevel = {
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
} as const

// ── Span names ───────────────────────────────────────────────────────────────

export const SpanName = {
  SCRAPER_RUN: 'scraper.run',
  PIPELINE_DISCOVER: 'pipeline.discover',
  PIPELINE_FETCH: 'pipeline.fetch',
  ARTICLE_PIPELINE: 'article.pipeline',
  ARTICLE_SCRAPED_HANDLE: 'article.scraped.handle',
  ARTICLE_PROCESSED_HANDLE: 'article.processed.handle',
  TAG_NORMALIZATION_HANDLE: 'article.tag_normalization.handle',
  ANALYSIS_COMPLETED_HANDLE: 'article.analysis_completed.handle',
  ARTICLE_TRANSLATE_HANDLE: 'article.translate.handle',
  ANALYSIS_FAILED_HANDLE: 'article.analysis_failed.handle',
  TAG_NORMALIZATION_FAILED_HANDLE: 'article.tag_normalization_failed.handle',
  TRANSLATION_FAILED_HANDLE: 'article.translation_failed.handle',
  PIPELINE_COMPLETED_HANDLE: 'scraper.pipeline_completed.handle',
  PIPELINE_COMPLETED_NOTIFY: 'scraper.pipeline_completed.notify',
  WEEKLY_REPORT_RUN: 'weekly_report.run',
  WEEKLY_REPORT_TOPIC: 'weekly_report.topic',
  WEEKLY_REPORT_SUMMARIZE: 'weekly_report.summarize',
  WEEKLY_REPORT_IMAGE: 'weekly_report.image',
  WEEKLY_REPORT_TRANSLATE: 'weekly_report.translate',
  WEEKLY_REPORT_NOTIFY: 'weekly_report.notify',
  REFRESH_METRICS_RUN: 'refresh_metrics.run',
  DEDUP_RECONCILE_RUN: 'dedup_reconcile.run',
} as const

// ── Span attributes ──────────────────────────────────────────────────────────

export const SpanAttribute = {
  RUN_ID: 'run.id',
  CORRELATION_ID: 'run.correlation_id',
  ARTICLE_TOPIC_ID: 'article.topic_id',
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

/** Build a TraceQL resource match with optional environment filter and service name override */
export function traceQLServiceMatch(env?: string, serviceName: string = SERVICE_NAME): string {
  const envClause = env ? ` && ${TraceQLResource.DEPLOYMENT_ENVIRONMENT} = "${env}"` : ''
  return `{ ${TraceQLResource.SERVICE_NAME} = "${serviceName}"${envClause} } | select(${TraceQLResource.DEPLOYMENT_ENVIRONMENT})`
}

/** Build a PromQL increase expression with optional by clause */
export function promqlIncrease(metric: string, range: string, byLabel?: string): string {
  const byClause = byLabel ? ` by (${byLabel})` : ''
  return `increase(${metric}[${range}])${byClause}`
}

/** PromQL label matcher for deployment_environment, e.g. `{deployment_environment="local"}` */
export function promqlEnvMatcher(env?: string): string {
  if (!env) return ''
  return `{${MetricLabelKey.DEPLOYMENT_ENVIRONMENT}="${env}"}`
}
