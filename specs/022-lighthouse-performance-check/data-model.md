# Data Model: Lighthouse Performance Check

This feature has no database entities — everything below is an in-memory/on-disk shape produced and consumed within a single script invocation. Documented here (rather than skipped) because the spec's Key Entities section names them explicitly and the consolidated report's structure depends on them.

## PerformanceCheckRun

One invocation of `make lighthouse-check`.

| Field | Type | Notes |
|---|---|---|
| `runId` | string | UTC timestamp, e.g. `20260809-143000`; used as the report output directory name |
| `baseUrl` | string | Resolved `BASE_URL` for this run (default `http://frontend_prod:3000`) |
| `routes` | `RouteTarget[]` | Resolved route list for this run (default: `/`, `/articles`, `/graph`, `/tags`) |
| `guestId` | string \| null | `guest_id` claim decoded from the pre-flight `POST /auth/guest` response; `null` only if that call itself failed (in which case the whole run aborts — see Edge Cases in spec.md) |
| `startedAt` / `finishedAt` | ISO 8601 string | Wall-clock bounds of the run, shown in the report header |

## RouteTarget

One configured route under test.

| Field | Type | Notes |
|---|---|---|
| `path` | string | e.g. `/articles` |
| `status` | `"success" \| "failed"` | |
| `failureReason` | string \| null | Human-readable cause (e.g. "HTTP 500", "Lighthouse timeout") when `status === "failed"`; `null` on success |
| `metrics` | `RouteMetrics \| null` | `null` when `status === "failed"` |
| `rawReportPath` | string | Path to that route's raw Lighthouse JSON, alongside the consolidated report |

## RouteMetrics

Extracted from a single route's Lighthouse JSON ("LHR") output.

| Field | Type | Source (LHR path) |
|---|---|---|
| `performanceScore` | integer, 0–100 | `categories.performance.score * 100`, rounded |
| `lcpMs` | number | `audits['largest-contentful-paint'].numericValue` |
| `tbtMs` | number | `audits['total-blocking-time'].numericValue` |
| `cls` | number | `audits['cumulative-layout-shift'].numericValue` |

## ConsolidatedReport

The Traditional-Chinese Markdown artifact produced at the end of a `PerformanceCheckRun`.

| Field | Type | Notes |
|---|---|---|
| `path` | string | `lighthouse-reports/<runId>/report.md` |
| `summaryTable` | one row per `RouteTarget` | Route, Performance/LCP/TBT/CLS (or 失敗原因 for failed routes) |
| `perRouteSections` | one section per `RouteTarget` | Narrative detail + link to that route's raw JSON |

No state transitions apply — every entity above is created once, populated, and written; nothing is updated in place after creation within a run.
