# Logging Contract

**Feature**: 006-observability | **Date**: 2026-05-29

## Structured Log Format

All log entries emitted by the system MUST conform to this JSON structure:

```json
{
  "event": "<event_name>",
  "level": "<severity>",
  "timestamp": "<ISO_8601>",
  "correlation_id": "<UUID4_or_empty>",
  "<key>": "<value>"
}
```

### Required Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| event | str | Caller | Event name passed to `logger.info(event, ...)` |
| level | str | structlog processor | Auto-added by `add_log_level` processor |
| timestamp | str | structlog processor | ISO 8601 format, added by `TimeStamper(fmt="iso")` |
| correlation_id | str | structlog processor | From ContextVar, added by `_add_correlation_id` processor |

### Request Log Additional Fields

Backend HTTP request logs include these additional fields:

| Field | Type | Source | Required |
|-------|------|--------|----------|
| method | str | HTTP request | Yes |
| path | str | HTTP request | Yes |
| status_code | int | HTTP response | Yes |
| duration_ms | float | Measured | Yes |
| user_id | str | JWT or "anonymous" | Yes |
| user_email | str | JWT | If authenticated |
| user_role | str | JWT | If authenticated |
| ip | str | request.client.host | Yes |
| user_agent | str | request header | Yes |
| geo_country | str | GeoIP lookup | If available |
| geo_city | str | GeoIP lookup | If available |

### Frontend Proxy Log Fields

| Field | Type | Source | Required |
|-------|------|--------|----------|
| event | str | "proxy_request" or "proxy_error" | Yes |
| method | str | HTTP request | Yes |
| path | str | URL path | Yes |
| status_code | int | Backend response | Yes |
| duration_ms | float | Measured | Yes |
| user_id | str | Server session | If authenticated |
| user_email | str | Server session | If authenticated |
| user_role | str | Server session | If authenticated |
| ip | str | x-forwarded-for | If present |
| user_agent | str | request header | If present |
| request_body | object | Request body (redacted) | For non-GET |

## Sensitive Field Redaction

The following keys MUST be redacted to `[REDACTED]` in any logged request body:

- password
- hashed_password
- token
- access_token
- refresh_token
- secret
- api_key
- authorization
- private_key
- credentials

Redaction is case-insensitive and recursive (nested objects are traversed).

## Loki Transport

- **Backend**: `python-logging-loki` LokiHandler attached to root Python logger
- **Frontend**: Direct HTTP POST to Loki push API (fire-and-forget)
- **Labels**: `{app: "scraper", env: "production"}` (backend), `{app: "frontend", env: NODE_ENV, level: <level>}` (frontend)
- **Auth**: HTTP Basic with `GRAFANA_LOKI_USER:GRAFANA_API_KEY`

## Metric Instruments

| Instrument Name | Type | Attributes | Description |
|-----------------|------|------------|-------------|
| scraper_runs_total | Counter | — | Total scraper run invocations |
| scraper_run_duration_seconds | Histogram | — | Duration of each run |
| scraper_articles_found_total | Counter | source | Articles discovered per source |
| scraper_articles_new_total | Counter | source | New articles per source |
| scraper_articles_duplicate_total | Counter | source | Duplicate articles per source |
| scraper_errors_total | Counter | source | Errors per source |

## Environment Variables

| Variable | Used By | Required For |
|----------|---------|-------------|
| GRAFANA_OTLP_USER | OTel metrics + tracing | Grafana Cloud OTLP |
| GRAFANA_API_KEY | OTel, Loki (backend + frontend) | Grafana Cloud auth |
| GRAFANA_OTLP_ENDPOINT | OTel metrics + tracing | Grafana Cloud OTLP |
| GRAFANA_LOKI_URL | Loki (backend + frontend) | Loki push |
| GRAFANA_LOKI_USER | Loki (backend + frontend) | Loki auth |
| SENTRY_DSN | Sentry (CLI entrypoints) | Error tracking |
| NEXTAUTH_SECRET | RequestLoggingMiddleware | JWT decode |
| GEOIP_DB_PATH | GeoIP | Custom DB path (default: /app/data/GeoLite2-City.mmdb) |
| TELEGRAM_BOT_TOKEN | TelegramNotifier | Pipeline notifications |
| TELEGRAM_CHAT_ID | TelegramNotifier | Pipeline notifications |
| GRAFANA_URL | Grafana embed proxy | Dashboard embedding |
| GRAFANA_SA_TOKEN | Grafana embed proxy | Grafana auth |
| BACKEND_URL | Frontend proxy | Backend URL (default: http://localhost:8000) |
