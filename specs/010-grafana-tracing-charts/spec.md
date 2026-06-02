# Feature Specification: Grafana Tracing & Custom Monitoring Charts

**Feature Branch**: `fix/grafana_trace_and_ui`

**Created**: 2026-05-31

**Status**: Complete — Phase 1–7 done; includes additional drill-down UI (Waterfall/Workflow dialogs) and global monitoring filter panel beyond original scope

**Input**: Fix OTel tracing pipeline to actually export spans to Grafana Cloud Tempo; replace broken Grafana image/iframe embedding in the monitoring dashboard with a native chart visualization approach that queries Grafana Cloud datasource APIs directly and renders charts client-side.

**Relation to existing spec**: Extends `006-observability` (brownfield). Spec 006 describes existing behavior; this spec defines the target state for two improvements that make the observability stack fully operational.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Sees Live Traces in Grafana Cloud Tempo (Priority: P1)

As an operator, I need to see distributed traces for each scraper run in Grafana Cloud Tempo so that I can understand which pipeline stage is slow or failing.

**Why this priority**: Without working traces, the "traces" observability pillar is completely absent. All the tracing code exists but produces no visible output.

**Independent Test**: Run a scraper cycle with Grafana Cloud credentials configured, then open Grafana Cloud Tempo and verify at least one trace is visible for that run.

**Acceptance Scenarios**:

1. **Given** Grafana Cloud tracing credentials are configured, **When** a scraper run completes, **Then** at least one trace with a `scraper.run` root span is visible in Grafana Cloud Tempo within 2 minutes.
2. **Given** Grafana Cloud tracing credentials are NOT configured, **When** a scraper run completes, **Then** the pipeline completes normally with no error related to tracing.
3. **Given** the trace export fails mid-run (network error), **When** the pipeline continues, **Then** the pipeline still completes and the failure is logged as a warning, not an exception.

---

### User Story 2 - Monitoring Dashboard Shows Live Charts (Priority: P1)

As an operator, I need the monitoring dashboard to display interactive, up-to-date charts for metrics, logs, and traces so that I can monitor system health without leaving the application or requiring paid Grafana Cloud features.

**Why this priority**: The current dashboard shows broken images (Grafana image renderer is not available on free tier). The monitoring page is non-functional.

**Independent Test**: Navigate to the admin monitoring page, verify at least one panel displays actual data as an interactive chart within 10 seconds.

**Acceptance Scenarios**:

1. **Given** Grafana Cloud credentials are configured, **When** the operator opens the monitoring dashboard, **Then** each panel loads and displays chart data within 10 seconds.
2. **Given** the monitoring dashboard is open, **When** the auto-refresh interval elapses, **Then** each chart refreshes its data without a full page reload.
3. **Given** Grafana Cloud credentials are NOT configured, **When** the operator opens the monitoring dashboard, **Then** each panel shows a clear "not configured" placeholder instead of a broken image or error.
4. **Given** a Grafana Cloud API call fails for one panel, **When** other panels load, **Then** the failing panel shows an error state and the remaining panels continue loading normally.

---

### User Story 3 - Operator Can Identify Pipeline Stage Bottlenecks (Priority: P2)

As an operator, I need traces to include spans for individual pipeline stages (scrape, process, analyze, translate) so that I can identify which stage is slow or failing across runs.

**Why this priority**: A single root span shows that a run happened but not where time is spent. Stage-level spans are needed for meaningful performance investigation.

**Independent Test**: Run a scraper cycle, then verify in Grafana Cloud Tempo that the trace contains at least three child spans representing distinct pipeline stages.

**Acceptance Scenarios**:

1. **Given** tracing is configured, **When** a scraper run executes, **Then** the trace contains child spans for at least: discovery, fetch, and analysis stages.
2. **Given** a pipeline stage fails, **When** the trace is inspected, **Then** the failing span shows error status and the exception message.
3. **Given** multiple sources are scraped, **When** the trace is inspected, **Then** per-source spans exist under the root span.

---

### Edge Cases

- What happens when the Grafana Cloud API returns a 429 (rate limit)? The panel shows cached or stale data with a visible staleness indicator; the error is logged but does not disrupt other panels.
- What happens when the chart data format changes (API schema change)? The panel shows an error state and the raw error is logged; the operator must update the query configuration.
- What happens when a trace is too large to export (many spans)? The BatchSpanProcessor drops older spans; only the most recent spans within the batch are exported.
- What happens when the operator opens the monitoring dashboard on a slow connection? Each panel loads independently; faster-loading panels appear immediately.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tracing pipeline MUST successfully export spans to Grafana Cloud Tempo when `GRAFANA_OTLP_USER`, `GRAFANA_API_KEY`, and `GRAFANA_OTLP_ENDPOINT` are all set.
- **FR-002**: Each scraper run MUST produce a root trace span (`scraper.run`) with at minimum: run ID, correlation ID, and total duration.
- **FR-003**: The pipeline MUST produce child spans for each major stage: source discovery, article fetch, article processing (dedup + save), LLM analysis, tag normalization, and translation. Each article MUST have a dedicated `article.pipeline` parent span grouping all its per-article handler spans.
- **FR-004**: The monitoring dashboard MUST fetch chart data by querying Grafana Cloud datasource APIs via a backend proxy; credentials MUST NOT be exposed to the client.
- **FR-005**: The backend MUST provide proxy endpoints for: Grafana Cloud Prometheus/Mimir queries (metrics), Loki queries (logs), Tempo search (traces list), and Tempo single-trace detail (`GET /grafana/traces/{id}`).
- **FR-006**: Each monitoring panel MUST auto-refresh at a configurable interval (default: 60 seconds).
- **FR-007**: When Grafana Cloud credentials are not configured, each monitoring panel MUST display a "not configured" placeholder rather than an error or broken image.
- **FR-008**: Each monitoring panel MUST display an error state independently when its data fetch fails, without affecting other panels.
- **FR-009**: The tracing provider MUST flush all pending spans before process exit.
- **FR-010**: When a Grafana Cloud API call fails during monitoring dashboard load, the error MUST be logged server-side and a structured error response returned to the client.
- **FR-011**: The monitoring dashboard MUST provide global filters (time range, deployment environment, log level) that apply to all batch queries across all tabs simultaneously.
- **FR-012**: The traces table MUST support expanding each run row to show per-article pipeline spans, and must allow drill-down into a Gantt-style waterfall view (span timeline) and a per-article workflow view (stage cards).
- **FR-013**: Failed-event spans (`analysis_failed`, `tag_normalization_failed`, `translation_failed`) MUST be recorded as ERROR-status spans in the trace, so failures are visible alongside successes in Tempo without any separate query.

### Key Entities

- **Trace**: A collection of spans representing a single scraper run, identified by a trace ID and visible in Grafana Cloud Tempo. The root span is `scraper.run`.
- **Article Pipeline Span** (`article.pipeline`): A per-article parent span created when `ArticleScrapedEvent` fires. It carries `article.url`, `article.source`, and `article.topic_id` attributes. All per-article handler spans (`article.scraped.handle`, `article.processed.handle`, etc.) are children of this span.
- **Stage Span**: A named unit of work within the pipeline (e.g., `pipeline.discover_and_fetch`, `pipeline.dedup`, `pipeline.publish_articles`, `article.pipeline`, `article.scraped.handle`) with start time, duration, and status. Naming convention: `{domain}.{operation}`.
- **Monitoring Panel**: A self-contained UI component that fetches data from a specific Grafana Cloud datasource and renders it as an interactive chart or table.
- **Datasource Proxy**: A backend API endpoint that accepts chart query parameters, authenticates to Grafana Cloud via per-datasource Basic Auth (`{user}:{api_key}`), and returns the data to the frontend.
- **Run Waterfall Dialog**: A modal showing all spans of a single trace as a Gantt chart (timeline bars), used for identifying slow stages at a glance.
- **Article Workflow Dialog**: A modal showing a single article's pipeline stages as sequential Langfuse-style stage cards, used for debugging per-article failures.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every scraper run with Grafana Cloud credentials configured produces at least one visible trace in Grafana Cloud Tempo within 2 minutes of run completion.
- **SC-002**: Every trace contains a minimum of 3 pipeline-level child spans (`pipeline.discover_and_fetch`, `pipeline.dedup`, `pipeline.publish_articles`) and at least one `article.pipeline` span per processed article, enabling identification of which stage and which article consumed the most time.
- **SC-003**: All monitoring dashboard panels load within 10 seconds when Grafana Cloud credentials are configured.
- **SC-004**: The monitoring dashboard is fully functional on Grafana Cloud free tier — no feature requires iframe embedding or the image renderer plugin.
- **SC-005**: A panel failure rate of zero cascades: one panel failing never causes other panels to fail or the page to crash.
- **SC-006**: Dashboard data is never stale by more than 2× the configured refresh interval under normal network conditions.

---

### User Story 4 - Monitoring Dashboard Uses Batch Queries with Per-Panel Refresh (Priority: P1)

As an operator, I need the monitoring dashboard to fetch all panel data in as few HTTP requests as possible, and to be able to manually refresh any individual panel, so that the page is efficient and interactive.

**Why this priority**: The current implementation fires one HTTP request per panel on load and on every 60-second interval, resulting in 5+ simultaneous requests per tab. Batching reduces server load and improves load time.

**Independent Test**: Open `/admin/monitoring` → DevTools Network tab → verify Operations tab fires at most 1 POST batch request on load (not 4+ individual GETs); click a panel's refresh icon → verify exactly 1 GET request fires for that panel only.

**Acceptance Scenarios**:

1. **Given** the monitoring dashboard loads an Operations/Logs/Traces tab, **When** the tab is first visited, **Then** all panels for that tab are populated from a single batch request per datasource type.
2. **Given** the monitoring dashboard is open, **When** the 60-second interval fires, **Then** all panels on the current tab refresh together via a single batch request.
3. **Given** a panel has a refresh icon, **When** the operator clicks it, **Then** only that panel re-fetches its data individually, and the spinner shows while loading.
4. **Given** Grafana Cloud is not configured, **When** the batch returns 503, **Then** all panels show "not configured" and the 60-second interval does not continue retrying.

---

## Assumptions

- Grafana Cloud free tier provides HTTP APIs for querying Prometheus/Mimir, Loki, and Tempo datasources; only the embed/iframe and image renderer features are restricted.
- The existing OTel SDK is already installed in the Python environment; no new Python dependency is needed for tracing itself.
- A frontend charting library will be added as a new npm dependency (Recharts, already popular in Next.js projects and tree-shakes well).
- The backend proxy for Grafana Cloud datasource queries uses per-datasource Basic Auth (`{DATASOURCE_USER}:{GRAFANA_API_KEY}`), not a shared service account token.
- Monitoring dashboard changes are scoped to the admin-only `/admin/monitoring` route; no changes to public-facing pages.
- The Grafana Cloud credentials (`GRAFANA_API_KEY`, datasource URLs, per-datasource user IDs) will be stored only in backend environment variables — never sent to the client.
- The Tempo, Loki, and Mimir datasource base URLs are separate environment variables from the existing `GRAFANA_OTLP_ENDPOINT` (ingest-only); each datasource also has a dedicated `_USER` variable for Basic Auth.
- Span wrappers (`with_span`, `with_span_deferred`, `with_article_pipeline_span`) are infrastructure-layer utilities and must not be called from the application layer.
