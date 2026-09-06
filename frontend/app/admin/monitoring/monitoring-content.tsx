'use client'

import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useI18n } from '@/lib/providers'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { MetricsChart } from '@/components/features/monitoring/metrics-chart'
import { CountryPanel } from '@/components/features/monitoring/country-panel'
import { LogsTable, type LogFilter } from '@/components/features/monitoring/logs-table'
import { LogFilterChip } from '@/components/features/monitoring/log-filter-chip'
import { TracesTable } from '@/components/features/monitoring/traces-table'
import {
  queryMetricsBatch, queryLokiMetricsBatch, queryLogsBatch,
  queryTracesBatch,
  type PrometheusResponse, type LokiResponse, type TempoResponse, type MetricsBatchItem,
} from '@/lib/api/grafana'
import { useAdminUsersStore } from '@/lib/stores/admin-users-store'
import { extractTraceSearchEnvironment } from '@/lib/otlp-utils'

/**
 * Loki's query_range endpoint (used for both metric-shaped Loki queries and raw log queries)
 * parses start/end as nanosecond-epoch strings, not unix-second integers — the batch endpoints
 * must agree on this or a stat count and the log table underneath it can silently query
 * different time windows despite using the identical LogQL filter.
 */
function toNs(sec: number): string {
  return (sec * 1000).toString() + '000000'
}
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  LogLevel, LokiLabel, LokiAppValue, SERVICE_NAME, SERVICE_NAME_BACKEND,
  lokiStreamSelector, traceQLServiceMatch,
} from '@/lib/observability-constants'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Dropdown } from '@/components/ui/dropdown'
import { RotateCw } from 'lucide-react'

// ── Types ──────────────────────────────────────────────────────────────────

type Environment = 'all' | 'local' | 'production' | string
type AppValue = typeof LokiAppValue[keyof typeof LokiAppValue]
type TimeRange = '6h' | '24h' | '3d' | '7d'

interface MonitoringFilters {
  timeRange: TimeRange
  environment: Environment
  app: AppValue
}

/** Resource service.name to filter Tempo traces by, per selected app. */
const APP_SERVICE_NAME: Record<AppValue, string> = {
  [LokiAppValue.SCRAPER]: SERVICE_NAME,
  [LokiAppValue.BACKEND]: SERVICE_NAME_BACKEND,
}

const TIME_RANGE_SECONDS: Record<TimeRange, number> = {
  '6h':  6 * 3600,
  '24h': 24 * 3600,
  '3d':  3 * 86400,
  '7d':  7 * 86400,
}

const TIME_RANGES: TimeRange[] = ['6h', '24h', '3d', '7d']

/** PromQL/LogQL range vector label covering the full selected duration */
function fullRangeVec(seconds: number): string {
  if (seconds < 3600) return `${Math.max(1, Math.round(seconds / 60))}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

/**
 * The actual tile size (both the chart's own count_over_time([...]) window and the Loki
 * query_range `step`) to use for a "trend" chart panel, given the selected time window.
 *
 * Every trend ChartPanelDef picks `step` to equal its own inner range-vector literal (a day for
 * daily-bucketed charts, an hour for hourly ones — see each panel's own comment), so `step`
 * doubles as the declared tile size. That tile must be clamped down to the selected window
 * (`totalRangeSeconds`) — otherwise a daily tile with the shortest selectable window (6h) is
 * bigger than the window itself.
 *
 * `renderAs: 'map'` is the one exception (currently just admin.requestsByCountryChart): its
 * consumer (CountryMap/CountryTable) reads only the query's *last* point rather than rendering
 * every point as its own bar (see lastValue() in country-map.tsx), so it already uses the
 * StatPanelDef convention — `step` there is a fixed per-point sampling rate, not a tile to
 * clamp, and must pass through unchanged.
 */
function effectiveChartStep(c: ChartPanelDef, totalRangeSeconds: number): number {
  const declared = parseInt(c.step, 10)
  return c.renderAs === 'map' ? declared : Math.min(declared, totalRangeSeconds)
}

/**
 * Computes the (rangeVec, start, end, step) a trend chart panel's query should actually use.
 *
 * Beyond clamping the tile (see effectiveChartStep), the query's own `start` is shifted forward
 * by that tile size. Without the shift, Loki's query_range always includes an extra point at
 * the raw `start` timestamp whose own trailing window reaches *before* the selected range even
 * began — for a short window that's the *only* point returned, so the chart would silently show
 * stale, out-of-range data instead of the requested window; for a longer window it shows up as
 * an extra leading bar that doesn't belong in the selected range either. Shifting `start`
 * forward by one tile makes the first returned point's own window start exactly at (or after)
 * the true beginning of the selected range.
 */
function chartFetchParams(
  c: ChartPanelDef, startSec: number, endSec: number, rangeVec: string,
): { rangeVec: string; start: number; end: number; step: number } {
  const step = effectiveChartStep(c, endSec - startSec)
  if (c.renderAs === 'map') return { rangeVec, start: startSec, end: endSec, step }
  return { rangeVec: fullRangeVec(step), start: startSec + step, end: endSec, step }
}

const DEFAULT_FILTERS: MonitoringFilters = {
  timeRange: '24h',
  environment: 'all',
  app: LokiAppValue.SCRAPER,
}

/** Swap the app="scraper" label baked into lokiStreamSelector() for the selected app. */
function applyAppToLokiQuery(query: string, app: AppValue): string {
  if (app === LokiAppValue.SCRAPER) return query
  return query.replace(/app="scraper"/g, `app="${app}"`)
}

function applyEnvToLokiQuery(query: string, environment: Environment): string {
  if (environment === 'all') return query
  const envLabel = `${LokiLabel.ENV}="${environment}"`
  return query
    .replace(/\{app="[^"]+"\}/g, m => `${m.slice(0, -1)}, ${envLabel}}`)
    .replace(/\{app="[^"]+", (?!env=)/g, m => `${m}${envLabel}, `)
}

/** Swap in the selected app, then layer the environment filter on top. */
function applyLokiFilters(query: string, app: AppValue, environment: Environment): string {
  return applyEnvToLokiQuery(applyAppToLokiQuery(query, app), environment)
}

interface MonitoringContentProps {
  grafanaUrl: string
  appEnv: string
}

// ── Panel descriptor types ─────────────────────────────────────────────────

interface StatPanelDef {
  titleKey: string
  buildQuery: (rangeVec: string, env?: string) => string
  step: string
  unit?: string
  tooltipKey: string
  queryType?: 'loki'
}

interface ChartPanelDef {
  titleKey: string
  buildQuery: (rangeVec: string, env?: string) => string
  step: string
  chartType?: 'line' | 'bar'
  height: number
  tooltipKey: string
  queryType?: 'loki'
  seriesColors?: Record<string, string>
  /** Renders via CountryMap instead of MetricsChart — same batched Loki query, different
   * visualization. Query must be grouped `by (geo_country)`. */
  renderAs?: 'map'
}

interface LogTablePanelDef {
  titleKey: string
  query: string
  height: number
  tooltipKey: string
}

interface TracesTablePanelDef {
  titleKey: string
  height: number
  tooltipKey: string
}

// ── Operations panel descriptors ───────────────────────────────────────────

// Fixed colors so "bot" reads the same (destructive red) as an error/warning elsewhere in this
// dashboard, and so MetricsChart's legend-when-single-series exception (see metrics-chart.tsx)
// kicks in — otherwise a window with zero bot traffic would render one unlabeled browser bar.
const CLIENT_TYPE_CHART_COLORS: Record<string, string> = {
  bot: 'hsl(347,74%,55%)',      // --destructive (dark) — matches LOG_LEVEL_CHART_COLORS.error
  browser: 'hsl(217,91%,60%)',  // matches COLORS[0] below
}

const OPS_SCRAPER_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.totalRuns',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [${rv}]))`,                                             step: '3600', tooltipKey: 'admin.totalRunsTooltip' },
  { queryType: 'loki', titleKey: 'admin.newArticles',       buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [${rv}]))`,                                           step: '3600', tooltipKey: 'admin.newArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.duplicateArticles', buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "article_duplicate_skipped" [${rv}]))`,                                    step: '3600', tooltipKey: 'admin.duplicateArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.errorCount',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" [${rv}]))`,                                        step: '3600', tooltipKey: 'admin.errorCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.failedArticles',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "llm_analysis_failed" [${rv}]))`,                                          step: '3600', tooltipKey: 'admin.failedArticlesTooltip' },
  { queryType: 'loki', titleKey: 'admin.articlesFound',     buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event =~ "analysis_completed|article_duplicate_skipped" [${rv}]))`,               step: '3600', tooltipKey: 'admin.articlesFoundTooltip' },
  { queryType: 'loki', titleKey: 'admin.recentRunDurationP100', buildQuery: rv => `max(max_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`, step: '3600', unit: 's', tooltipKey: 'admin.recentRunDurationP100Tooltip' },
  { queryType: 'loki', titleKey: 'admin.avgDurationP50',        buildQuery: rv => `avg(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`, step: '3600', unit: 's', tooltipKey: 'admin.avgDurationP50Tooltip' },
]

const OPS_SCRAPER_CHARTS: ChartPanelDef[] = [
  // Daily tile: count_over_time([rv]) + step=86400, both clamped down (see effectiveChartStep)
  // when the selected window is shorter than a day — so each point = that day's article count
  // for a multi-day window, or the whole window's count as a single point for a sub-day one.
  { queryType: 'loki', titleKey: 'admin.articleVolumeChart',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [${rv}]))`,                                                                       step: '86400', height: 240, tooltipKey: 'admin.articleVolumeChartTooltip' },
  // avg() collapses per-run series from unwrap into a single time series
  { queryType: 'loki', titleKey: 'admin.runDurationChart',      buildQuery: rv => `avg(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`,                                               step: '3600',  height: 240, tooltipKey: 'admin.runDurationChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.articlesBySourceChart', buildQuery: rv => `sum by (source) (count_over_time(${lokiStreamSelector()} | json | event = "analysis_completed" [${rv}]))`,                                                          step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.articlesBySourceChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.errorsByTypeChart',     buildQuery: rv => `sum by (event) (count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" | json | event != "" [${rv}]))`,                                    step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.errorsByTypeChartTooltip' },
]

// 020-redis-caching-layer verification: shared/cache/redis_gateway.py emits one "cache_lookup"
// event per get_or_set() call (namespace/status/lang), covering every cached endpoint
// (articles/graph/tag_groups/weekly_reports) from a single choke point, plus a
// "cache_*_failed" event per Redis error (read/write/version/decode/bump/warmup-publish).
// RequestLoggingMiddleware (backend/middleware/logging.py) emits one "request" event per
// HTTP request (method/path/status_code/duration_ms). Both are backend-only signals — this
// panel set is only shown/queried when FilterBar's App selector is "backend" (see
// OperationsTab and its useOperationsBatch() call in MonitoringContent).
const OPS_BACKEND_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.cacheHitRate',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="cache_lookup" | status="HIT" [${rv}])) / sum(count_over_time(${lokiStreamSelector()} | json | event="cache_lookup" [${rv}])) * 100`, step: '3600', unit: '%', tooltipKey: 'admin.cacheHitRateTooltip' },
  { queryType: 'loki', titleKey: 'admin.requestCount',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,                                                    step: '3600', tooltipKey: 'admin.requestCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.requestErrorRate',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="request" | status_code >= 500 [${rv}])) / sum(count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}])) * 100`, step: '3600', unit: '%', tooltipKey: 'admin.requestErrorRateTooltip' },
  // quantile_over_time (not avg_over_time) — a true percentile, unlike avg() which one slow
  // outlier can barely move. avg() wrapper just collapses to one series if there's ever more
  // than one backend replica; with a single replica it's a no-op.
  { queryType: 'loki', titleKey: 'admin.requestDurationP50',    buildQuery: rv => `avg(quantile_over_time(0.5, ${lokiStreamSelector()} | json | event="request" | unwrap duration_ms [${rv}]))`,                     step: '3600', unit: 'ms', tooltipKey: 'admin.requestDurationP50Tooltip' },
  { queryType: 'loki', titleKey: 'admin.requestDurationP90',    buildQuery: rv => `avg(quantile_over_time(0.9, ${lokiStreamSelector()} | json | event="request" | unwrap duration_ms [${rv}]))`,                     step: '3600', unit: 'ms', tooltipKey: 'admin.requestDurationP90Tooltip' },
  { queryType: 'loki', titleKey: 'admin.cacheFailureCount',   buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event=~"cache_read_failed|cache_write_failed|cache_version_read_failed|cache_version_malformed|cache_decode_failed|cache_bump_version_failed|cache_warmup_publish_failed" [${rv}]))`, step: '3600', tooltipKey: 'admin.cacheFailureCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.chatRequestCount',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="chat_request" [${rv}]))`,                                                step: '3600', tooltipKey: 'admin.chatRequestCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.searchQueryCount',    buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event=~"search_query_executed|search_autocomplete_executed" [${rv}]))`,        step: '3600', tooltipKey: 'admin.searchQueryCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.searchFallbackRate',  buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="search_autocomplete_executed" | source="postgres_fallback" [${rv}])) / sum(count_over_time(${lokiStreamSelector()} | json | event="search_autocomplete_executed" [${rv}])) * 100`, step: '3600', unit: '%', tooltipKey: 'admin.searchFallbackRateTooltip' },
  // Loki has no native distinct-count aggregation — `count(count by (user_id) (...))` is the
  // documented LogQL idiom: the inner query promotes user_id into a per-series label (one
  // series per distinct value seen in the window), the outer count() counts those series. Works
  // uniformly across roles now that guest traffic carries a stable per-visitor fingerprint
  // instead of the literal "anonymous" for everyone (see _extract_user()'s guest_id fallback).
  { queryType: 'loki', titleKey: 'admin.uniqueVisitors',      buildQuery: rv => `count(count by (user_id) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}])))`, step: '3600', tooltipKey: 'admin.uniqueVisitorsTooltip' },
  { queryType: 'loki', titleKey: 'admin.botRequestRate',      buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="request" | client_type="bot" [${rv}])) / sum(count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}])) * 100`, step: '3600', unit: '%', tooltipKey: 'admin.botRequestRateTooltip' },
]

const OPS_BACKEND_CHARTS: ChartPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.cacheLookupsByStatusChart',     buildQuery: rv => `sum by (status) (count_over_time(${lokiStreamSelector()} | json | event="cache_lookup" [${rv}]))`,                          step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.cacheLookupsByStatusChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.cacheHitRateByNamespaceChart',  buildQuery: rv => `sum by (namespace) (count_over_time(${lokiStreamSelector()} | json | event="cache_lookup" | status="HIT" [${rv}])) / sum by (namespace) (count_over_time(${lokiStreamSelector()} | json | event="cache_lookup" [${rv}])) * 100`, step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.cacheHitRateByNamespaceChartTooltip' },
  // avg() collapses per-request series from unwrap into a single time series, same shape as admin.runDurationChart
  { queryType: 'loki', titleKey: 'admin.requestDurationTrendChart',     buildQuery: rv => `avg(avg_over_time(${lokiStreamSelector()} | json | event="request" | unwrap duration_ms [${rv}]))`,                          step: '3600',  height: 240, tooltipKey: 'admin.requestDurationTrendChartTooltip' },
  // topk(10, ...) on all by-label breakdowns below — path/country cardinality is unbounded
  // (every distinct route or every visiting country becomes its own bar/series), so without a
  // cap a busy day turns the chart into an unreadable wall of slivers instead of a ranked list.
  { queryType: 'loki', titleKey: 'admin.requestsByPathChart',           buildQuery: rv => `topk(10, sum by (path) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}])))`,                        step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.requestsByPathChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.requestErrorsByPathChart',      buildQuery: rv => `topk(10, sum by (path) (count_over_time(${lokiStreamSelector()} | json | event="request" | status_code >= 400 [${rv}])))`,    step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.requestErrorsByPathChartTooltip' },
  // No topk cap here (unlike the path/error breakdowns above) — a choropleth is naturally
  // bounded to ~174 countries by geography, and capping to a top-N would wrongly render
  // every country outside it as "no traffic" gray instead of its actual (smaller) count.
  // Grouped by geo_city and user_role too (unbounded, but CountryTable is the only consumer of
  // that extra granularity — CountryMap's extractCountryTotals sums back down to geo_country,
  // ignoring the role label entirely) so all three panels share this one query result instead
  // of CountryTable firing a second query just for its per-country role-mix bar.
  //
  // Unlike every other chart below, this one's *consumer* (CountryMap/CountryTable) collapses
  // the whole series down to one static total per country instead of rendering a per-bucket
  // trend — so it uses the StatPanelDef convention instead of these other charts' hardcoded
  // `[1d]` daily-tile pattern: `rv` is the *entire* selected time range (not a fixed day), and
  // `step: '3600'` guarantees a point lands exactly on "now" for all four time-range filter
  // options (6h/24h/3d/7d are all whole multiples of an hour) — extractCountryTotals &co. then
  // read only that last point (see lastValue() in country-map.tsx). The old `[1d]`/step=86400
  // pairing double-counted: summing every returned point included one extra trailing day of
  // stale data outside the selected window, for every one of the four filter options.
  { queryType: 'loki', titleKey: 'admin.requestsByCountryChart',        buildQuery: rv => `sum by (user_role, geo_country, geo_city) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,                                 step: '3600', height: 240, renderAs: 'map', tooltipKey: 'admin.requestsByCountryChartTooltip' },
  // backend/middleware/logging.py's _extract_user() always sets user_role (defaults to
  // "guest" for no-token/guest-token/decode-failure), so this always shows a real
  // guest/user/admin split instead of guest traffic falling into an unlabeled "(other)" bucket.
  { queryType: 'loki', titleKey: 'admin.requestsByRoleChart',           buildQuery: rv => `sum by (user_role) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,                                step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.requestsByRoleChartTooltip' },
  // Same count-distinct idiom as admin.uniqueVisitors, kept per-role here instead of collapsed
  // to one scalar.
  { queryType: 'loki', titleKey: 'admin.uniqueVisitorsByRoleChart',     buildQuery: rv => `count by (user_role) (count by (user_role, user_id) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}])))`, step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.uniqueVisitorsByRoleChartTooltip' },
  { queryType: 'loki', titleKey: 'admin.requestsByClientTypeChart',     buildQuery: rv => `sum by (client_type) (count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,                              step: '86400', height: 240, chartType: 'bar', tooltipKey: 'admin.requestsByClientTypeChartTooltip', seriesColors: CLIENT_TYPE_CHART_COLORS },
]

// ── Logs panel descriptors ─────────────────────────────────────────────────

const LOG_LEVEL_CHART_COLORS: Record<string, string> = {
  error: 'hsl(347,74%,55%)',   // --destructive (dark)
  warn:  'hsl(48,96%,53%)',    // yellow-500
  info:  'hsl(0,0%,55%)',      // --muted-foreground solid equivalent
}

const LOGS_VOLUME_CHART: ChartPanelDef = {
  titleKey: 'admin.logVolumeChart',
  buildQuery: rv => `sum by (${LokiLabel.DETECTED_LEVEL}) (count_over_time(${lokiStreamSelector()}[${rv}]))`,
  step: '60',
  height: 180,
  tooltipKey: 'admin.logVolumeChartTooltip',
  seriesColors: LOG_LEVEL_CHART_COLORS,
}

const LOGS_STAT_PANELS: StatPanelDef[] = [
  { titleKey: 'admin.logErrorCount',   buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.ERROR}" [${rv}]))`, step: '3600', tooltipKey: 'admin.logErrorCountTooltip' },
  { titleKey: 'admin.logWarningCount', buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "warn" [${rv}]))`,              step: '3600', tooltipKey: 'admin.logWarningCountTooltip' },
]

// Error → Warning → Info order
const LOGS_TABLE_PANELS: LogTablePanelDef[] = [
  { titleKey: 'admin.errorLogs',   query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.ERROR}"`, height: 300, tooltipKey: 'admin.errorLogsTooltip' },
  { titleKey: 'admin.warningLogs', query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "warn"`,              height: 300, tooltipKey: 'admin.warningLogsTooltip' },
  { titleKey: 'admin.infoLogs',    query: `${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "${LogLevel.INFO}"`,  height: 300, tooltipKey: 'admin.infoLogsTooltip' },
]

// ── Traces panel descriptors ───────────────────────────────────────────────
// Split the same way Operations is (see OPS_SCRAPER_*/OPS_BACKEND_*): "execution_started"/
// "execution_completed" are scraper-run-lifecycle events, meaningless for backend HTTP
// traffic, so backend gets its own stat/chart set built from the "request" event instead.

const TRACES_SCRAPER_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.tracesCount',       buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [${rv}]))`,                                   step: '3600', tooltipKey: 'admin.tracesCountTooltip' },
  { queryType: 'loki', titleKey: 'admin.avgRunDurationP95', buildQuery: rv => `max(avg_over_time(${lokiStreamSelector()} | json | event = "execution_completed" | unwrap duration_seconds [${rv}]))`,         step: '3600', unit: 's', tooltipKey: 'admin.avgRunDurationP95Tooltip' },
  { queryType: 'loki', titleKey: 'admin.errorSpans',        buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" [${rv}]))`,                                step: '3600', tooltipKey: 'admin.errorSpansTooltip' },
]

const TRACES_SCRAPER_SPAN_CHART: ChartPanelDef = {
  queryType: 'loki',
  titleKey: 'admin.spanRateChart',
  // 1h tile + step=3600 (instead of 5m/300) prevents 576-point range and sparse gaps
  buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event = "execution_started" [${rv}]))`,
  step: '3600',
  height: 240,
  tooltipKey: 'admin.spanRateChartTooltip',
}

const TRACES_BACKEND_STATS: StatPanelDef[] = [
  { queryType: 'loki', titleKey: 'admin.tracesCount',          buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,                                            step: '3600', tooltipKey: 'admin.tracesCountBackendTooltip' },
  { queryType: 'loki', titleKey: 'admin.requestDurationP95',   buildQuery: rv => `avg(quantile_over_time(0.95, ${lokiStreamSelector()} | json | event="request" | unwrap duration_ms [${rv}]))`,               step: '3600', unit: 'ms', tooltipKey: 'admin.requestDurationP95Tooltip' },
  { queryType: 'loki', titleKey: 'admin.errorSpans',           buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | ${LokiLabel.DETECTED_LEVEL} = "error" [${rv}]))`,                               step: '3600', tooltipKey: 'admin.errorSpansTooltip' },
]

const TRACES_BACKEND_SPAN_CHART: ChartPanelDef = {
  queryType: 'loki',
  titleKey: 'admin.requestRateChart',
  buildQuery: rv => `sum(count_over_time(${lokiStreamSelector()} | json | event="request" [${rv}]))`,
  step: '3600',
  height: 240,
  tooltipKey: 'admin.requestRateChartTooltip',
}

const TRACES_TABLE_PANEL: TracesTablePanelDef = {
  titleKey: 'admin.recentTraces',
  height: 400,
  tooltipKey: 'admin.recentTracesTooltip',
}

// ── Shared helper ──────────────────────────────────────────────────────────

/**
 * Fetches once per distinct `fetchAll` identity while the tab is active, instead of
 * refetching every time the tab merely becomes active again. `fetchAll` is a
 * useCallback keyed on the query params (time range, environment, app), so its
 * identity only actually changes when those params (or a manual Refresh) change —
 * switching tabs back and forth with unchanged filters becomes a no-op.
 */
function useFetchOnceWhenActive(fetchAll: () => Promise<void>, enabled: boolean) {
  const fetchedForRef = useRef<typeof fetchAll | null>(null)
  useEffect(() => {
    if (!enabled || fetchedForRef.current === fetchAll) return
    fetchedForRef.current = fetchAll
    fetchAll()
  }, [fetchAll, enabled])
}

function extractLastValue(res: PrometheusResponse): string | undefined {
  if ('error' in res) return undefined
  if (res.status === 'success' && res.data?.result.length) {
    const vals = res.data.result[0].values
    if (vals.length) return parseFloat(vals[vals.length - 1][1]).toFixed(1).replace(/\.0$/, '')
  }
  return '0'
}

// ── Operations batch hook ──────────────────────────────────────────────────

/**
 * Generic over `stats`/`charts` so the same hook drives both the Scraper and Backend
 * operations sub-tabs (each with its own panel set and its own fixed `app` value) —
 * see the two useOperationsBatch() calls in MonitoringContent.
 */
function useOperationsBatch(
  startSec: number, endSec: number, environment: Environment, app: AppValue, enabled: boolean,
  stats: StatPanelDef[], charts: ChartPanelDef[],
) {
  const env = environment === 'all' ? undefined : environment
  const rangeVec = fullRangeVec(endSec - startSec)

  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(stats.length).fill(undefined))
  const [chartData, setChartData] = useState<(PrometheusResponse | null)[]>(Array(charts.length).fill(null))
  const [loading, setLoading] = useState<boolean[]>(Array(stats.length + charts.length).fill(true))

  const fetchAll = useCallback(async () => {
    setLoading(Array(stats.length + charts.length).fill(true))
    const promItems: MetricsBatchItem[] = [
      ...stats.filter(s => s.queryType !== 'loki').map(s => ({ query: s.buildQuery(rangeVec, env), start: startSec, end: endSec, step: s.step })),
      ...charts.filter(c => c.queryType !== 'loki').map(c => {
        const p = chartFetchParams(c, startSec, endSec, rangeVec)
        return { query: c.buildQuery(p.rangeVec, env), start: p.start, end: p.end, step: String(p.step) }
      }),
    ]
    const lokiItems = [
      ...stats.filter(s => s.queryType === 'loki').map(s => ({ query: applyLokiFilters(s.buildQuery(rangeVec), app, environment), start: toNs(startSec), end: toNs(endSec), step: s.step })),
      ...charts.filter(c => c.queryType === 'loki').map(c => {
        const p = chartFetchParams(c, startSec, endSec, rangeVec)
        return { query: applyLokiFilters(c.buildQuery(p.rangeVec), app, environment), start: toNs(p.start), end: toNs(p.end), step: String(p.step) }
      }),
    ]
    try {
      const [promResults, lokiResults] = await Promise.all([
        promItems.length > 0 ? queryMetricsBatch(promItems) : Promise.resolve([]),
        lokiItems.length > 0 ? queryLokiMetricsBatch(lokiItems) : Promise.resolve([]),
      ])
      const promNotConfigured = promItems.length > 0 && 'error' in promResults[0] && (promResults[0] as { error: string }).error === 'not_configured'
      const lokiNotConfigured = lokiItems.length > 0 && 'error' in lokiResults[0] && (lokiResults[0] as { error: string }).error === 'not_configured'
      if (promNotConfigured || lokiNotConfigured) {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        setChartData(Array(charts.length).fill(err))
        setLoading(Array(stats.length + charts.length).fill(false))
        return
      }
      const newStatValues: (string | undefined)[] = new Array(stats.length).fill(undefined)
      let pi = 0, li = 0
      for (let i = 0; i < stats.length; i++) {
        newStatValues[i] = stats[i].queryType === 'loki'
          ? extractLastValue(lokiResults[li++] as PrometheusResponse)
          : extractLastValue(promResults[pi++])
      }
      const newChartData: (PrometheusResponse | null)[] = []
      for (let i = 0; i < charts.length; i++) {
        newChartData.push(charts[i].queryType === 'loki'
          ? lokiResults[li++] as PrometheusResponse
          : promResults[pi++] as PrometheusResponse)
      }
      setStatValues(newStatValues)
      setChartData(newChartData)
    } catch { /* keep previous data */ } finally {
      setLoading(Array(stats.length + charts.length).fill(false))
    }
  }, [startSec, endSec, rangeVec, env, environment, app, stats, charts])

  useFetchOnceWhenActive(fetchAll, enabled)

  return { statValues, chartData, loading, refresh: fetchAll }
}

// ── Logs batch hook ────────────────────────────────────────────────────────

const LOGS_NUM_METRIC = 1 + LOGS_STAT_PANELS.length

function useLogsBatch(startSec: number, endSec: number, environment: Environment, app: AppValue, enabled: boolean) {
  const env = environment === 'all' ? undefined : environment
  const rangeVec = fullRangeVec(endSec - startSec)

  const [metricData, setMetricData] = useState<(PrometheusResponse | null)[]>(Array(LOGS_NUM_METRIC).fill(null))
  const [logsData, setLogsData] = useState<(LokiResponse | null)[]>(Array(LOGS_TABLE_PANELS.length).fill(null))
  const [loading, setLoading] = useState<boolean[]>(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))

  const fetchAll = useCallback(async () => {
    setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(true))
    const startNs = toNs(startSec)
    const endNs = toNs(endSec)
    // LOGS_VOLUME_CHART is a trend chart (unlike LOGS_STAT_PANELS) — its own 1-minute tile,
    // query start, and step need the same clamp-and-shift as OPS_*_CHARTS (see chartFetchParams).
    const volumeParams = chartFetchParams(LOGS_VOLUME_CHART, startSec, endSec, rangeVec)
    try {
      const [metricResults, logsResults] = await Promise.all([
        queryLokiMetricsBatch([
          {
            query: applyLokiFilters(LOGS_VOLUME_CHART.buildQuery(volumeParams.rangeVec, env), app, environment),
            step: String(volumeParams.step), start: toNs(volumeParams.start), end: toNs(volumeParams.end),
          },
          ...LOGS_STAT_PANELS.map(p => ({
            query: applyLokiFilters(p.buildQuery(rangeVec, env), app, environment),
            step: p.step, start: startNs, end: endNs,
          })),
        ]),
        queryLogsBatch(LOGS_TABLE_PANELS.map(p => ({
          query: applyLokiFilters(p.query, app, environment),
          start: startNs, end: endNs, limit: 500,
        }))),
      ])
      if ('error' in metricResults[0] && (metricResults[0] as { error: string }).error === 'not_configured') {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const logsErr = { error: 'not_configured' } as unknown as LokiResponse
        setMetricData(Array(LOGS_NUM_METRIC).fill(err))
        setLogsData(Array(LOGS_TABLE_PANELS.length).fill(logsErr))
        setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
        return
      }
      setMetricData(metricResults as PrometheusResponse[])
      setLogsData(logsResults as LokiResponse[])
    } catch { /* keep previous data */ } finally {
      setLoading(Array(LOGS_NUM_METRIC + LOGS_TABLE_PANELS.length).fill(false))
    }
  }, [startSec, endSec, rangeVec, env, environment, app])

  useFetchOnceWhenActive(fetchAll, enabled)

  return { metricData, logsData, loading, refresh: fetchAll }
}

// ── Traces batch hook ──────────────────────────────────────────────────────

function useTracesBatch(
  startSec: number, endSec: number, environment: Environment, app: AppValue, enabled: boolean,
  stats: StatPanelDef[], spanChart: ChartPanelDef,
) {
  const rangeVec = fullRangeVec(endSec - startSec)

  const [statValues, setStatValues] = useState<(string | undefined)[]>(Array(stats.length).fill(undefined))
  const [chartData, setChartData] = useState<PrometheusResponse | null>(null)
  const [tracesData, setTracesData] = useState<TempoResponse | null>(null)
  const [loading, setLoading] = useState<boolean[]>(Array(stats.length + 2).fill(true))

  // Tempo's TraceQL search filtered on a generic resource attribute like
  // resource.deployment.environment has been observed to return results many hours stale
  // (its live/head block search appears to only reliably cover a handful of intrinsic
  // fields such as service.name) — the identical query without that attribute filter, or a
  // trace-by-ID lookup, returns fully fresh data. So this never sends an environment filter
  // to Tempo; `| select(...)` (still applied when env is undefined) asks Tempo to attach the
  // attribute to each search result so it can be filtered here on the client instead. When a
  // specific environment is selected, over-fetch more candidates than the eventual display
  // count — a single environment's traffic can be a small fraction of "all environments"
  // recent traces once fetched unfiltered-by-env.
  const traceQuery = traceQLServiceMatch(undefined, APP_SERVICE_NAME[app])
  const traceFetchLimit = environment === 'all' ? 20 : 100
  const traceDisplayLimit = 20

  const fetchAll = useCallback(async () => {
    setLoading(Array(stats.length + 2).fill(true))
    try {
      // spanChart is a trend chart (unlike `stats`) — same clamp-and-shift as OPS_*_CHARTS.
      const spanParams = chartFetchParams(spanChart, startSec, endSec, rangeVec)
      const lokiItems = [
        ...stats.map(s => ({ query: applyLokiFilters(s.buildQuery(rangeVec), app, environment), step: s.step, start: toNs(startSec), end: toNs(endSec) })),
        { query: applyLokiFilters(spanChart.buildQuery(spanParams.rangeVec), app, environment), step: String(spanParams.step), start: toNs(spanParams.start), end: toNs(spanParams.end) },
      ]
      const [lokiResults, tracesResults] = await Promise.all([
        queryLokiMetricsBatch(lokiItems),
        queryTracesBatch([{ q: traceQuery, start: startSec, end: endSec, limit: traceFetchLimit }]),
      ])
      if ('error' in lokiResults[0] && (lokiResults[0] as { error: string }).error === 'not_configured') {
        const err = { error: 'not_configured' } as unknown as PrometheusResponse
        const tracesErr = { error: 'not_configured' } as unknown as TempoResponse
        setChartData(err)
        setTracesData(tracesErr)
        setLoading(Array(stats.length + 2).fill(false))
        return
      }
      setStatValues(lokiResults.slice(0, stats.length).map(r => extractLastValue(r as PrometheusResponse)))
      setChartData(lokiResults[stats.length] as PrometheusResponse)

      const rawTraces = tracesResults[0] as TempoResponse
      const hasTracesError = 'error' in (rawTraces as unknown as Record<string, unknown>)
      setTracesData(
        !hasTracesError && environment !== 'all'
          ? { ...rawTraces, traces: rawTraces.traces.filter(t => extractTraceSearchEnvironment(t) === environment).slice(0, traceDisplayLimit) }
          : rawTraces
      )
    } catch { /* keep previous data */ } finally {
      setLoading(Array(stats.length + 2).fill(false))
    }
  }, [startSec, endSec, rangeVec, environment, app, traceQuery, traceFetchLimit, traceDisplayLimit, stats, spanChart])

  useFetchOnceWhenActive(fetchAll, enabled)

  return { statValues, chartData, tracesData, loading, refresh: fetchAll }
}

// ── Tab sub-components ─────────────────────────────────────────────────────

/** Renders one operations panel set — shared by the Scraper and Backend panel sets so they
 * stay visually identical apart from their content. CSS grid auto-wraps, so `stats`/`charts`
 * don't need to be a fixed length (unlike the Scraper set, Backend keeps growing new panels). */
function OpsStatsChartsGrid({
  stats, charts, statValues: sv, chartData: cd, loading, timeRangeSeconds, rangeLabel,
}: {
  stats: StatPanelDef[]
  charts: ChartPanelDef[]
  statValues: (string | undefined)[]
  chartData: (PrometheusResponse | null)[]
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const { t } = useI18n()
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3 mt-4">
        {stats.map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        {charts.map((p, i) => (
          p.renderAs === 'map' ? (
            // CountryPanel renders the map and table as two direct grid children (side by
            // side in one row) sharing one selection state, both reading the same fetched
            // result (cd[i]) — no second query just for the table.
            <CountryPanel key={i} mapTitle={t(p.titleKey, { range: rangeLabel })} mapTooltip={t(p.tooltipKey, { range: rangeLabel })}
              tableTitle={t('admin.requestsByCountryTable', { range: rangeLabel })} tableTooltip={t('admin.requestsByCountryTableTooltip', { range: rangeLabel })}
              height={p.height} data={cd[i]} loading={loading[stats.length + i]} />
          ) : (
            <MetricsChart key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" step={String(effectiveChartStep(p, timeRangeSeconds))} height={p.height}
              chartType={p.chartType} timeRangeSeconds={timeRangeSeconds}
              externalData={cd[i]} externalLoading={loading[stats.length + i]}
              seriesColors={p.seriesColors}
              tooltip={t(p.tooltipKey, { range: rangeLabel })} />
          )
        ))}
      </div>
    </div>
  )
}

/** Which panel set Operations shows switches on the same top-level App filter that already
 * drives Logs/Traces (FilterBar's `app`) — one uniform "which app am I looking at" control
 * across all three tabs, instead of a separate selector just for Operations. */
function OperationsTab({
  app, statValues, chartData, loading, timeRangeSeconds, rangeLabel,
}: {
  app: AppValue
  statValues: (string | undefined)[]
  chartData: (PrometheusResponse | null)[]
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const isBackend = app === LokiAppValue.BACKEND
  return (
    <OpsStatsChartsGrid
      stats={isBackend ? OPS_BACKEND_STATS : OPS_SCRAPER_STATS}
      charts={isBackend ? OPS_BACKEND_CHARTS : OPS_SCRAPER_CHARTS}
      statValues={statValues} chartData={chartData} loading={loading}
      timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
  )
}

function LogsTab({
  app, metricData: md, logsData: ld, loading, timeRangeSeconds, rangeLabel, callerNames,
}: {
  app: AppValue
  metricData: (PrometheusResponse | null)[]
  logsData: (LokiResponse | null)[]
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
  callerNames: Record<string, string>
}) {
  const showRequestColumns = app === LokiAppValue.BACKEND
  const { t } = useI18n()
  // country / session_id are backend "request"-event fields — drop the filter whenever the App
  // selector switches, so a stale (and now column-less) filter can't hide every scraper row.
  // Adjusting state during render on a changed prop, per the React "previous render" pattern —
  // avoids the extra commit an effect would cost.
  const [logFilter, setLogFilter] = useState<LogFilter | null>(null)
  const [filterApp, setFilterApp] = useState(app)
  if (filterApp !== app) {
    setFilterApp(app)
    setLogFilter(null)
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-6 gap-3 mt-4">
        <MetricsChart title={t(LOGS_VOLUME_CHART.titleKey, { range: rangeLabel })} query="unused" step={String(effectiveChartStep(LOGS_VOLUME_CHART, timeRangeSeconds))}
          height={LOGS_VOLUME_CHART.height} className="col-span-4" timeRangeSeconds={timeRangeSeconds}
          externalData={md[0]} externalLoading={loading[0]}
          seriesColors={LOGS_VOLUME_CHART.seriesColors}
          tooltip={t(LOGS_VOLUME_CHART.tooltipKey, { range: rangeLabel })} />
        {LOGS_STAT_PANELS.map((p, i) => (
          <div key={i} className="col-span-1">
            <StatCard title={t(p.titleKey, { range: rangeLabel })} value={md[i + 1] ? extractLastValue(md[i + 1]!) : undefined}
              loading={loading[i + 1]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
          </div>
        ))}
      </div>
      {showRequestColumns && <LogFilterChip filter={logFilter} onClear={() => setLogFilter(null)} />}
      <div className="space-y-3">
        {LOGS_TABLE_PANELS.map((p, i) => (
          <LogsTable key={i} title={t(p.titleKey, { range: rangeLabel })} query="unused" height={p.height}
            externalData={ld[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })}
            showRequestColumns={showRequestColumns} callerNames={callerNames}
            logFilter={logFilter} onLogFilterChange={setLogFilter} />
        ))}
      </div>
    </div>
  )
}

function TracesTab({
  app, grafanaUrl, statValues: sv, chartData: cd, tracesData: td, loading, timeRangeSeconds, rangeLabel,
}: {
  app: AppValue
  grafanaUrl?: string
  statValues: (string | undefined)[]
  chartData: PrometheusResponse | null
  tracesData: TempoResponse | null
  loading: boolean[]
  timeRangeSeconds: number
  rangeLabel: string
}) {
  const { t } = useI18n()
  const isBackend = app === LokiAppValue.BACKEND
  const stats = isBackend ? TRACES_BACKEND_STATS : TRACES_SCRAPER_STATS
  const spanChart = isBackend ? TRACES_BACKEND_SPAN_CHART : TRACES_SCRAPER_SPAN_CHART
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 mt-4">
        {stats.map((p, i) => (
          <StatCard key={i} title={t(p.titleKey, { range: rangeLabel })} value={sv[i]} unit={p.unit}
            loading={loading[i]} tooltip={t(p.tooltipKey, { range: rangeLabel })} />
        ))}
      </div>
      <MetricsChart title={t(spanChart.titleKey, { range: rangeLabel })} query="unused" step={String(effectiveChartStep(spanChart, timeRangeSeconds))}
        height={spanChart.height} timeRangeSeconds={timeRangeSeconds}
        externalData={cd} externalLoading={loading[stats.length]}
        tooltip={t(spanChart.tooltipKey, { range: rangeLabel })} />
      <TracesTable title={t(TRACES_TABLE_PANEL.titleKey, { range: rangeLabel })} query="unused" height={TRACES_TABLE_PANEL.height}
        grafanaUrl={grafanaUrl} externalData={td}
        tooltip={t(TRACES_TABLE_PANEL.tooltipKey, { range: rangeLabel })} />
    </div>
  )
}

// ── Filter bar ─────────────────────────────────────────────────────────────

function FilterBar({
  filters, onChange, appEnv,
}: {
  filters: MonitoringFilters
  onChange: (f: MonitoringFilters) => void
  appEnv: string
}) {
  const { t } = useI18n()
  return (
    <div className="flex flex-wrap gap-4 items-center pb-4 border-b border-border">
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-muted-foreground">{t('admin.filterTimeRange')}:</span>
        <div className="flex gap-1">
          {TIME_RANGES.map(tr => (
            <button
              key={tr}
              onClick={() => onChange({ ...filters, timeRange: tr })}
              className={cn(
                'text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer',
                filters.timeRange === tr
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground',
              )}
            >
              {tr}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-xs">
        <span className="text-muted-foreground">{t('admin.filterApp')}:</span>
        <Dropdown
          size="sm"
          value={filters.app}
          onChange={v => onChange({ ...filters, app: v as AppValue })}
          options={[
            { value: LokiAppValue.SCRAPER, label: 'Scraper' },
            { value: LokiAppValue.BACKEND, label: 'Backend' },
          ]}
        />
      </div>
      {appEnv === 'local' && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">{t('admin.filterEnvironment')}:</span>
          <Dropdown
            size="sm"
            value={filters.environment}
            onChange={v => onChange({ ...filters, environment: v as Environment })}
            options={[
              { value: 'all', label: t('admin.filterAll') },
              { value: 'local', label: 'local' },
              { value: 'staging', label: 'staging' },
              { value: 'production', label: 'production' },
              { value: 'test', label: 'test' },
            ]}
          />
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function MonitoringContent({ grafanaUrl, appEnv }: MonitoringContentProps) {
  const { t } = useI18n()
  const { data: session } = useSession()
  const adminToken = (session as any)?.accessToken
  // Shared cache (frontend/lib/stores/admin-users-store.ts) — also used by the User
  // Management page, so whichever page loads first is the only one that ever calls
  // GET /auth/users. Only used here to resolve the Logs tab's Caller column from a raw
  // user_id (the bearer JWT never carries email/username — see backend/services/auth_service.py's
  // create_user_access_token) to something readable.
  const { users: adminUsers, ensureLoaded: ensureAdminUsersLoaded } = useAdminUsersStore()
  useEffect(() => {
    if (adminToken) ensureAdminUsersLoaded(adminToken)
  }, [adminToken, ensureAdminUsersLoaded])
  const callerNames = useMemo(
    () => Object.fromEntries(adminUsers.map(u => [u.id, u.username ?? u.name ?? u.email ?? u.id])),
    [adminUsers],
  )

  const [filters, setFilters] = useState<MonitoringFilters>(DEFAULT_FILTERS)
  // refreshKey increments on manual Refresh so startSec/endSec update to current time
  const [refreshKey, setRefreshKey] = useState(0)
  // Only the active tab's hook actually fetches — each tab's batch endpoint fans out into
  // several concurrent upstream Grafana queries, so fetching all three tabs at once (regardless
  // of which one is visible) multiplies that fan-out and made the dashboard prone to 503s from
  // Grafana Cloud rate limiting.
  const [activeTab, setActiveTab] = useState('operations')

  const timeRangeSeconds = TIME_RANGE_SECONDS[filters.timeRange]
  const rangeLabel = filters.timeRange
  const effectiveEnv: Environment = appEnv === 'local' ? filters.environment : appEnv

  const [startSec, endSec] = useMemo(() => {
    const now = Math.floor(Date.now() / 1000)
    return [now - timeRangeSeconds, now]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRangeSeconds, refreshKey])

  const isBackendApp = filters.app === LokiAppValue.BACKEND
  const { statValues: opsSV, chartData: opsCd, loading: opsLoading } = useOperationsBatch(
    startSec, endSec, effectiveEnv, filters.app, activeTab === 'operations',
    isBackendApp ? OPS_BACKEND_STATS : OPS_SCRAPER_STATS, isBackendApp ? OPS_BACKEND_CHARTS : OPS_SCRAPER_CHARTS)
  const { metricData: logsMd, logsData: logsLd, loading: logsLoading } = useLogsBatch(startSec, endSec, effectiveEnv, filters.app, activeTab === 'logs')
  const { statValues: tracesSV, chartData: tracesCd, tracesData: tracesTd, loading: tracesLoading } = useTracesBatch(
    startSec, endSec, effectiveEnv, filters.app, activeTab === 'traces',
    isBackendApp ? TRACES_BACKEND_STATS : TRACES_SCRAPER_STATS, isBackendApp ? TRACES_BACKEND_SPAN_CHART : TRACES_SCRAPER_SPAN_CHART)

  const activeLoading = activeTab === 'operations' ? opsLoading : activeTab === 'logs' ? logsLoading : tracesLoading
  const isLoading = activeLoading.some(Boolean)

  // Incrementing refreshKey updates startSec/endSec → only the active tab's hook re-fetches.
  // Manual only (via the Refresh button below) — no auto-refresh timer. An idle tab's time
  // window does freeze at whatever "now" was on last refresh/mount until the operator clicks
  // Refresh; that's the deliberate tradeoff (was previously a 60s setInterval).
  function handleRefresh() { setRefreshKey(k => k + 1) }

  return (
    <TooltipProvider>
      <div className="max-w-7xl space-y-6">
        <div className="border-b border-border pb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">{t('admin.monitoring')}</h1>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading} className="gap-1.5">
            <RotateCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
            {t('admin.refreshPage')}
          </Button>
        </div>

        <FilterBar filters={filters} onChange={setFilters} appEnv={appEnv} />

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="operations">{t('admin.operations')}</TabsTrigger>
            <TabsTrigger value="logs">{t('admin.logs')}</TabsTrigger>
            <TabsTrigger value="traces">{t('admin.traces')}</TabsTrigger>
          </TabsList>

          <TabsContent value="operations">
            <OperationsTab app={filters.app} statValues={opsSV} chartData={opsCd} loading={opsLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
          </TabsContent>
          <TabsContent value="logs">
            <LogsTab app={filters.app} metricData={logsMd} logsData={logsLd} loading={logsLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} callerNames={callerNames} />
          </TabsContent>
          <TabsContent value="traces">
            <TracesTab app={filters.app} grafanaUrl={grafanaUrl} statValues={tracesSV} chartData={tracesCd}
              tracesData={tracesTd} loading={tracesLoading}
              timeRangeSeconds={timeRangeSeconds} rangeLabel={rangeLabel} />
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  )
}
