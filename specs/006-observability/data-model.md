# Data Model: Observability

**Feature**: 006-observability | **Date**: 2026-05-29

This is a brownfield feature — no new database tables or ORM models. The observability stack operates on events, context variables, and external service APIs. This document describes the in-memory and context-based data structures used by observability components.

## Entities

### Metric Instrument

| Field | Type | Description |
|-------|------|-------------|
| name | str | OTel instrument name (e.g., `scraper_runs_total`) |
| kind | Counter \| Histogram | Instrument type |
| value | int \| float | Current accumulated value |
| attributes | dict[str, str] | Per-call labels (e.g., `{"source": "rss"}`) |

**Instruments defined** (module-level in `otel_metrics.py`):

| Name | Kind | Description |
|------|------|-------------|
| `scraper_runs_total` | Counter | Total number of scraper runs |
| `scraper_run_duration_seconds` | Histogram | Duration of each scraper run |
| `scraper_articles_found_total` | Counter | Total articles discovered |
| `scraper_articles_new_total` | Counter | New (non-duplicate) articles |
| `scraper_articles_duplicate_total` | Counter | Duplicate articles skipped |
| `scraper_errors_total` | Counter | Errors encountered per source |

### Run Context

| Field | Type | Storage | Description |
|-------|------|---------|-------------|
| run_id | str (UUID4) | ContextVar | Unique identifier for the current scraper run |
| correlation_id | str (UUID4) | ContextVar | Bound into structlog context for log correlation |

### Log Entry

| Field | Type | Description |
|-------|------|-------------|
| level | str | Log severity (info, warning, error, etc.) |
| timestamp | str (ISO 8601) | Event timestamp |
| correlation_id | str | Run-scoped correlation identifier |
| event | str | Event name/description |
| * | any | Additional event-specific key-value pairs |

### Request Log (extends Log Entry)

| Field | Type | Description |
|-------|------|-------------|
| method | str | HTTP method |
| path | str | Request path |
| status_code | int | Response status |
| duration_ms | float | Request duration in milliseconds |
| user_id | str \| "anonymous" | Authenticated user ID |
| user_email | str \| absent | User email (if authenticated) |
| user_role | str \| absent | User role (if authenticated) |
| ip | str | Client IP address |
| user_agent | str | Client user-agent |
| geo_country | str \| absent | Country from GeoIP lookup |
| geo_city | str \| absent | City from GeoIP lookup |

### Notification Message

| Field | Type | Description |
|-------|------|-------------|
| chat_id | str | Telegram chat ID |
| text | str (MarkdownV2) | Formatted pipeline summary |
| parse_mode | str | Always "MarkdownV2" |

### GeoIP Lookup Result

| Field | Type | Description |
|-------|------|-------------|
| country | str | ISO country code (e.g., "TW") |
| city | str | City name (e.g., "Taipei") |

**Note**: Returns `{}` on any failure (missing DB, invalid IP, lookup error).

## Relationships

```text
PipelineCompletedEvent
├── OtelMetricsHandler → SCRAPER_ARTICLES_NEW.add(new, {source})
│                       → SCRAPER_ARTICLES_DUPLICATE.add(duplicate, {source})
│                       → SCRAPER_ERRORS.add(failed, {source})
└── NotificationHandler → TelegramNotifier.notify(event)

Scraper Run (main.py)
├── init_run_context() → (run_id, correlation_id)
├── bind_correlation_id(correlation_id) → ContextVar
├── SCRAPER_RUNS.add(1)
├── tracer.start_as_current_span("scraper.run", attrs={run.id, run.correlation_id})
└── finally: SCRAPER_DURATION.record(duration)
            push_metrics()
            shutdown_tracing()

HTTP Request (backend)
├── RequestLoggingMiddleware
│   ├── request_id (UUID4) → X-Request-ID header
│   ├── _extract_user(request) → user_id/email/role
│   ├── get_geo(ip) → geo_country/geo_city
│   └── logger.info("request", ...) → structlog → stdout + Loki
└── languages.py
    └── resolve_language_from_ip(ip) → get_geo(ip) → "zh-TW" | "en"

Frontend Proxy
├── handler(request) → forward to backend
└── pushToLoki({event, method, path, status, duration, user, ip, user_agent, body})
    └── redact(body) → replace sensitive keys with [REDACTED]
```
