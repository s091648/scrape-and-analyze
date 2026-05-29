# Implementation Plan: Observability

**Branch**: `006-observability` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-observability/spec.md`

## Summary

Brownfield documentation and test coverage for the existing observability stack: OTel metrics/traces to Grafana Cloud, structlog+Loki logging, Sentry error tracking, GeoIP resolution, RequestLoggingMiddleware, Telegram notifications, frontend proxy logging, and Grafana embed proxy. All components follow a graceful no-op fallback pattern when their backends are unconfigured.

## Technical Context

**Language/Version**: Python 3.11 (backend/scraper), TypeScript 5.x / React 19 (frontend)

**Primary Dependencies**: opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http, structlog>=24.0, python-logging-loki>=0.3, sentry-sdk, geoip2>=4.8, Starlette (BaseHTTPMiddleware), Next.js 16 (App Router)

**Storage**: PostgreSQL 15 + pgvector (for app data — observability uses external SaaS backends)

**Testing**: pytest (unit via `make test`, integration via `make test-integration`), Vitest (frontend unit), Playwright (frontend E2E)

**Target Platform**: Docker containers (Linux), Railway (production)

**Project Type**: Web application (scraper + FastAPI backend + Next.js frontend)

**Performance Goals**: No impact on pipeline throughput when observability is disabled; sub-ms overhead per log/metric call when enabled

**Constraints**: All observability components must gracefully degrade to no-op when unconfigured (constitution VI)

**Scale/Scope**: ~22 source files across 3 services, 8 existing test files with 17 test functions, ~9 identified test gaps

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. DDD | PASS | Observability code lives in `src/infrastructure/shared/` — correct layer. Re-export facades in `__init__.py` follow existing pattern. |
| II. Atomic Frontend | PASS | `loki-logger.ts` and `grafana-embed/route.ts` are infrastructure, not UI components. No new components needed. |
| III. Test Discipline | PASS | All new tests will use `make test` (Docker). Integration tests use isolated schemas. |
| IV. Docker-First | PASS | No changes to dev workflow. Tests run in Docker per constitution. |
| V. CI-Only Deployment | PASS | No CI/CD changes. |
| VI. Observability First-Class | PASS | This IS the observability spec — documenting and testing existing compliance. |
| VII. Code Style | PASS | Python follows PEP 8, TypeScript strict mode. No new production code expected (brownfield verification). |

**Gate Result**: PASS — all principles satisfied. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/006-observability/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── logging-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── infrastructure/
│   ├── shared/
│   │   ├── observability/
│   │   │   ├── __init__.py         # Facade: re-exports metrics, tracing, run_context
│   │   │   ├── otel_metrics.py     # OTel metrics: 6 instruments + _Dummy no-op
│   │   │   ├── otel_tracing.py     # OTel tracing: TracerProvider + no-op fallback
│   │   │   ├── loki_logging.py     # Loki handler + stdout fallback
│   │   │   ├── run_context.py      # Run ID + correlation ID ContextVars
│   │   │   └── geoip.py            # Re-export of shared.utils.geoip
│   │   ├── logging.py              # structlog config + correlation_id processor
│   │   └── notifications/
│   │       ├── __init__.py         # Re-exports NotificationHandler, factory
│   │       ├── base_notifier.py    # BaseNotifier ABC
│   │       ├── telegram.py         # TelegramNotifier
│   │       └── notification_service.py  # NotificationHandler + build_notification_handler
│   └── collection/
│       └── handlers/
│           └── otel_metrics_handler.py  # PipelineCompletedEvent → OTel counters
├── shared/
│   └── logging.py                  # get_logger() facade for domain code
├── entrypoints/
│   └── cli/
│       ├── main.py                 # Scraper CLI: full observability init/teardown
│       └── translate.py            # Translate CLI: Sentry + logging only
└── config/
    └── settings.py                 # SENTRY_DSN + other env vars

backend/
├── middleware/
│   └── logging.py                  # RequestLoggingMiddleware
├── routers/
│   └── languages.py               # GeoIP-based language resolution
├── main.py                         # FastAPI app + middleware wiring
└── tests/
    └── test_request_logging_middleware.py

frontend/
├── lib/
│   └── loki-logger.ts              # pushToLoki() fire-and-forget
└── app/
    └── api/
        ├── proxy/[...path]/route.ts  # BFF proxy with Loki logging
        └── grafana-embed/route.ts    # Grafana embed proxy with SSRF guard

shared/
└── utils/
    └── geoip.py                    # MaxMind GeoLite2 lazy singleton

src/tests/unit/
├── infrastructure/shared/
│   ├── test_logging.py
│   ├── observability/
│   │   ├── test_observability.py
│   │   ├── test_tracing.py
│   │   └── test_geoip.py
│   └── notifications/
│       ├── test_telegram_notifier.py
│       └── test_notification_handler.py
└── modules/collection/application/
    ├── test_otel_metrics_handler.py
    └── test_notification_handler.py
```

**Structure Decision**: Brownfield — no structural changes. All directories and files already exist. The plan documents the existing architecture and identifies test gaps to fill.

## Complexity Tracking

No violations. This is a brownfield verification spec — no new production code complexity introduced.
