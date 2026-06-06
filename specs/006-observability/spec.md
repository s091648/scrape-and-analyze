# Feature Specification: Observability

**Feature Branch**: `006-observability`

**Created**: 2026-05-29

**Status**: Draft

**Input**: Brownfield spec — describe existing observability behavior in present tense, covering OTel metrics/traces, structlog+Loki logging, Sentry error tracking, GeoIP resolution, request logging, Telegram notifications, and their graceful no-op fallback patterns.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Monitors Scraping Pipeline Health (Priority: P1)

As a system operator, I need to see real-time metrics about scraper runs (run count, duration, articles found/new/duplicate, errors) so that I can detect anomalies and ensure the pipeline is functioning correctly.

**Why this priority**: Metrics are the primary visibility mechanism; without them, the operator is blind to pipeline health.

**Independent Test**: Can be fully tested by running a scrape cycle and verifying that metric counters and histograms are emitted to the configured backend. Delivers visibility into pipeline throughput and error rates.

**Acceptance Scenarios**:

1. **Given** the OTel metrics backend is configured, **When** a scraper run completes, **Then** the system increments `scraper_runs_total`, records duration in `scraper_run_duration_seconds`, and reports per-source counts for new/duplicate/failed articles.
2. **Given** the OTel metrics backend is NOT configured, **When** a scraper run completes, **Then** metric calls silently no-op and the pipeline completes without errors.

---

### User Story 2 - Operator Investigates Issues via Structured Logs (Priority: P1)

As a system operator, I need all application events emitted as structured JSON logs with correlation IDs so that I can trace requests across services and diagnose issues in Loki or container stdout.

**Why this priority**: Structured logging with correlation IDs is foundational for all debugging workflows; it enables cross-referencing between logs, traces, and metrics.

**Independent Test**: Can be fully tested by triggering any operation and verifying JSON-structured log output to stdout with correlation_id fields. Delivers the ability to trace request flows end-to-end.

**Acceptance Scenarios**:

1. **Given** the logging system is initialized, **When** any application event is logged, **Then** the log entry is emitted as JSON with `level`, `timestamp` (ISO 8601), `correlation_id`, and event-specific fields.
2. **Given** the Loki backend is configured, **When** log entries are emitted, **Then** they are pushed to Loki with labels `app=scraper` and `env=production`.
3. **Given** the Loki backend is NOT configured, **When** log entries are emitted, **Then** they appear only on stdout and the application runs normally.

---

### User Story 3 - Operator Receives Pipeline Completion Notifications (Priority: P2)

As a system operator, I need to receive a Telegram message after each scraping pipeline run completes, summarizing per-source statistics (new/duplicate/failed), total counts, and run duration, so that I am proactively informed of pipeline outcomes.

**Why this priority**: Push notifications provide proactive awareness without requiring dashboard monitoring, but they depend on the pipeline already running (P1 stories).

**Independent Test**: Can be fully tested by running a scrape cycle and verifying a Telegram message is sent with the expected summary format. Delivers proactive operational awareness.

**Acceptance Scenarios**:

1. **Given** Telegram credentials are configured, **When** a pipeline run completes, **Then** a MarkdownV2-formatted message is sent to the configured chat with per-source stats table, totals, duration, and success/error indicator.
2. **Given** Telegram credentials are NOT configured, **When** a pipeline run completes, **Then** no notification is attempted and the pipeline completes normally.
3. **Given** the Telegram API call fails at runtime, **When** the notifier attempts to send, **Then** the error is caught and logged, and the pipeline continues without interruption.

---

### User Story 4 - Operator Traces Requests Across Services (Priority: P2)

As a system operator, I need distributed traces for scraper runs so that I can understand the flow of requests through the system and identify latency bottlenecks.

**Why this priority**: Traces complement metrics and logs by showing temporal flow, but metrics and logs are typically consulted first during investigation.

**Independent Test**: Can be fully tested by running a scraper cycle and verifying OTel spans are exported. Delivers the ability to visualize request flow and identify slow components.

**Acceptance Scenarios**:

1. **Given** the OTel tracing backend is configured, **When** a scraper run starts, **Then** a span named `scraper.run` is created and subsequent operations occur within its context.
2. **Given** the OTel tracing backend is NOT configured, **When** a scraper run starts, **Then** no-op spans are created and the application runs normally.

---

### User Story 5 - Developer Captures Unhandled Errors via Sentry (Priority: P2)

As a developer, I need unhandled exceptions in the CLI scraper and translator entrypoints automatically reported to Sentry so that I am alerted to production errors without relying on manual log inspection.

**Why this priority**: Automated error reporting reduces mean time to detection, but only applies to CLI entrypoints (not the backend API).

**Independent Test**: Can be fully tested by causing an exception in the CLI entrypoint and verifying it appears in Sentry. Delivers automated error alerting for the scraper process.

**Acceptance Scenarios**:

1. **Given** `SENTRY_DSN` is configured, **When** the CLI scraper or translator entrypoint starts, **Then** the Sentry SDK is initialized with 10% trace sampling rate.
2. **Given** `SENTRY_DSN` is NOT configured, **When** the CLI entrypoint starts, **Then** Sentry SDK is not loaded and the application runs without error tracking.

---

### User Story 6 - API Consumer Sees Request IDs for Support (Priority: P3)

As an API consumer, I need each HTTP response to include a `X-Request-ID` header so that I can reference specific requests when reporting issues to the operator.

**Why this priority**: Request IDs support support workflows but are not needed for core pipeline operation.

**Independent Test**: Can be fully tested by making any HTTP request to the backend and verifying the `X-Request-ID` header is present and unique. Delivers traceability for API support.

**Acceptance Scenarios**:

1. **Given** any HTTP request arrives at the backend, **When** the response is returned, **Then** it includes an `X-Request-ID` header with a unique identifier.
2. **Given** an authenticated request, **When** the middleware logs the request, **Then** the log entry includes user identity (user_id, email, role) and request metadata (method, path, status, duration, IP, user agent).
3. **Given** an unauthenticated request, **When** the middleware logs the request, **Then** user identity shows as `anonymous`.

---

### User Story 7 - Frontend Operator Sees Proxy Request Logs (Priority: P3)

As a system operator, I need frontend proxy requests logged to Loki with request metadata and redacted sensitive fields, so that I can monitor API traffic patterns from the frontend without exposing secrets.

**Why this priority**: Frontend request logging completes the observability picture but the backend middleware already covers the primary use case.

**Independent Test**: Can be fully tested by making requests through the frontend proxy and verifying Loki entries with redacted sensitive fields. Delivers end-to-end request visibility.

**Acceptance Scenarios**:

1. **Given** Loki is configured on the frontend, **When** a request passes through the proxy route, **Then** a Loki entry is pushed with method, path, status, duration, user identity, IP, and user agent.
2. **Given** a request body contains sensitive fields (password, token, api_key, etc.), **When** the proxy logs the request, **Then** those fields are replaced with `[REDACTED]`.
3. **Given** Loki is NOT configured on the frontend, **When** a request passes through the proxy, **Then** the proxy functions normally without logging.

---

### User Story 8 - Visitor Sees Localized Content via GeoIP (Priority: P3)

As a website visitor, I need the system to automatically detect my country from my IP address so that content is presented in my preferred language.

**Why this priority**: GeoIP enhances user experience but is a secondary feature that falls back gracefully to English.

**Independent Test**: Can be fully tested by making requests from different IP addresses and verifying language resolution. Delivers automatic localization.

**Acceptance Scenarios**:

1. **Given** the GeoIP database is available, **When** a visitor from Taiwan accesses the site, **Then** the language resolver returns `zh-TW`.
2. **Given** the GeoIP database is available, **When** a visitor from any other country accesses the site, **Then** the language resolver returns `en`.
3. **Given** the GeoIP database is NOT available, **When** any visitor accesses the site, **Then** the language resolver defaults to `en`.

---

### User Story 9 - Operator Views Embedded Grafana Dashboards (Priority: P3)

As an authenticated user, I need to view Grafana dashboard panels embedded in the application UI, proxied through the backend with SSRF protection, so that I can monitor system health without switching tools.

**Why this priority**: Dashboard embedding is a convenience feature; Grafana can always be accessed directly.

**Independent Test**: Can be fully tested by navigating to an embedded Grafana panel URL and verifying the proxy forwards the request. Delivers integrated monitoring.

**Acceptance Scenarios**:

1. **Given** the user is authenticated and Grafana credentials are configured, **When** the user requests an embedded dashboard, **Then** the request is proxied to the configured Grafana instance with a service account token.
2. **Given** the target URL does not start with the configured Grafana base URL, **When** a request is made, **Then** it is rejected (SSRF protection).
3. **Given** the user is not authenticated, **When** the user requests an embedded dashboard, **Then** the request is rejected with a 401 status.

---

### Edge Cases

- What happens when OTel export fails mid-run? The pipeline continues; metrics for that run may be partially lost.
- What happens when the GeoIP database file exists but is corrupted? The lookup returns an empty result; the caller falls back gracefully.
- What happens when Loki push fails from the frontend? The error is caught and logged to console.error; the request still completes normally (fire-and-forget).
- What happens when the Sentry SDK itself throws during initialization? The exception propagates; the entrypoint may fail to start.
- What happens when the Telegram API returns a non-OK response? `raise_for_status()` is called, but the NotificationHandler catches the exception and logs a warning, allowing other notifiers (if any) to proceed.
- What happens when the logging system is initialized more than once? The structlog configuration is overwritten; the last `configure_logging()` call wins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST emit structured JSON logs with `level`, `timestamp` (ISO 8601), `correlation_id`, and event-specific fields for every application event.
- **FR-002**: The system MUST push structured logs to Loki when Loki credentials are configured; otherwise logs MUST appear only on stdout.
- **FR-003**: The system MUST emit scraper pipeline metrics (runs total, run duration, articles found/new/duplicate, errors) to an OTel-compatible backend when OTel credentials are configured; otherwise metric calls MUST silently no-op.
- **FR-004**: The system MUST create a `scraper.run` span for each scraper run when OTel tracing is configured; otherwise span creation MUST silently no-op.
- **FR-005**: The system MUST flush and shut down OTel metrics and tracing providers at process exit.
- **FR-006**: The system MUST initialize Sentry error tracking in CLI entrypoints when `SENTRY_DSN` is configured; otherwise Sentry MUST not be loaded.
- **FR-007**: The system MUST generate a unique request ID (UUID4) for every HTTP request to the backend API and include it as an `X-Request-ID` response header.
- **FR-008**: The system MUST log every HTTP request with method, path, status code, duration, user identity (or anonymous), IP, user agent, and optional GeoIP fields.
- **FR-009**: The system MUST resolve visitor country from IP address when the GeoIP database is available; otherwise MUST default to English.
- **FR-010**: The system MUST send a Telegram notification on pipeline completion when Telegram credentials are configured; otherwise no notification MUST be attempted.
- **FR-011**: The system MUST redact sensitive fields (password, token, api_key, authorization, etc.) from logged request bodies in the frontend proxy.
- **FR-012**: The system MUST proxy Grafana embed requests with SSRF protection (only URLs under the configured Grafana base URL) and require authentication.
- **FR-013**: The system MUST push frontend proxy request logs to Loki when configured; otherwise the proxy MUST function without logging.
- **FR-014**: The system MUST bind a correlation ID into the logging context for each scraper run so that all log entries within a run share the same correlation ID.
- **FR-015**: The system MUST generate a unique run ID for each scraper run and make it available via context variable.

### Key Entities

- **Metric Instrument**: A named counter or histogram that records quantitative data about scraper operations (e.g., `scraper_runs_total`, `scraper_run_duration_seconds`).
- **Log Entry**: A structured JSON record with correlation metadata (level, timestamp, correlation_id) and event-specific fields.
- **Request Log**: A specialized log entry for HTTP requests containing method, path, status, duration, user identity, IP, and optional geo fields.
- **Notification Message**: A formatted summary of pipeline results (per-source stats, totals, duration, status) delivered to an external channel.
- **GeoIP Lookup Result**: A country/city pair resolved from an IP address, or an empty result when the database is unavailable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every scraper run produces a complete set of metrics (6 instruments) when the metrics backend is available, or completes without error when it is not.
- **SC-002**: Every log entry across all services contains a `correlation_id` field, enabling cross-service request tracing.
- **SC-003**: Every HTTP response from the backend includes a `X-Request-ID` header with a unique value.
- **SC-004**: Pipeline completion notifications are delivered within 5 seconds of run completion when Telegram is configured, or silently skipped when not.
- **SC-005**: Sensitive fields are never present in frontend proxy logs — all redacted keys are replaced with `[REDACTED]`.
- **SC-006**: The application starts and operates normally when any single observability backend is unavailable, with no functional degradation of core pipeline behavior.
- **SC-007**: Sentry captures unhandled exceptions in CLI entrypoints within the 10% trace sampling rate when configured.

## Assumptions

- All observability backends (OTel/Grafana Cloud, Loki, Sentry) are external SaaS services; the system does not host them.
- The `GRAFANA_API_KEY` is shared across OTel, Loki (backend), and Loki (frontend) integrations.
- The GeoIP database file is pre-provisioned at the expected path (e.g., via a download script using `MAXMIND_LICENSE_KEY`); the runtime code only reads it.
- Sentry is only initialized in CLI entrypoints (scraper and translator), not in the backend API or frontend.
- Telegram notifications are only triggered on `PipelineCompletedEvent`, not on individual article processing events.
- The observability stack is entirely optional: the system is designed to run with zero observability backends configured (dev/local mode) with graceful no-op fallbacks for every component.
- The frontend proxy logs to Loki using a fire-and-forget pattern — log delivery is not guaranteed.
- The `NotificationHandler` pattern supports multiple notifiers, but currently only Telegram is implemented.
