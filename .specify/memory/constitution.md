<!--
Sync Impact Report:
- Version change: N/A → 1.0.0 (initial constitution)
- Modified principles: N/A (new document)
- Added sections: All (Core Principles, Technology Stack, Development Workflow, Governance)
- Removed sections: N/A
- Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ compatible (Constitution Check section exists)
  - .specify/templates/spec-template.md: ✅ compatible (requirements structure aligns)
  - .specify/templates/tasks-template.md: ✅ compatible (phase structure aligns)
- Follow-up TODOs: None
-->

# Scrape-and-Analyze Constitution

## Core Principles

### I. Domain-Driven Design (NON-NEGOTIABLE)

The `src/` service MUST follow hexagonal/DDD architecture with strict
layer separation:

- **Domain layer** (`src/modules/*/domain/`): Entities, value objects,
  repository interfaces, and domain service interfaces. Zero dependency
  on infrastructure or application code.
- **Application layer** (`src/modules/*/application/`): Use cases, event
  handlers, DTOs, and application events. Depends only on domain layer
  interfaces.
- **Infrastructure layer** (`src/infrastructure/`): Concrete
  implementations of scrapers, LLM providers, repositories, parsers,
  notifications, and observability. Implements domain interfaces.
- **Composition root** (`src/bootstrap.py`): Manual dependency wiring;
  no DI container. All cross-layer assembly happens here.

Rationale: DDD prevents domain logic leakage into infrastructure and
keeps the scraper pipeline testable, replaceable, and resilient to
provider changes.

### II. Atomic Frontend Architecture

Frontend components MUST follow a modified atomic design hierarchy:

- **`components/ui/`** — Shadcn/UI primitives (atomic): button, card,
  dialog, table, etc. Never import domain logic.
- **`components/common/`** — Shared molecules: date-filter,
  error-boundary, multi-select-popover. Compose from `ui/` atoms.
- **`components/features/`** — Domain organisms organized by feature
  (`articles/`, `graph/`, `monitoring/`, `tags/`, etc.). May consume
  common molecules and ui atoms.
- **`components/providers/`** — Context providers (Session, Topic, I18n,
  ErrorBoundary). Wrap at layout level only.

Rationale: Clear component boundaries prevent feature coupling and keep
UI primitives reusable across admin and public routes.

### III. Test Discipline

- **Python**: pytest with `@pytest.mark.integration` for DB-dependent
  tests. Unit tests MUST NOT require a running database. Integration
  tests MUST use isolated schemas (`test_integration`, `backend_test`)
  with per-test rollback via savepoints.
- **Frontend**: Vitest for unit tests (exclude `components/ui/`
  Shadcn primitives from coverage). Playwright for E2E (chromium).
  Storybook for component visual testing.
- **Test isolation**: Integration test conftest MUST create and tear
  down isolated PostgreSQL schemas. Backend integration conftest MUST
  use savepoint-based transaction wrapping so endpoint `db.commit()`
  does not escape the outer rollback.
- **CI gates**: Unit tests run first; integration/E2E only after unit
  pass. Coverage uploaded to Codecov with carryforward.

Rationale: Isolated, deterministic tests prevent flaky CI and ensure
fast feedback loops. Schema isolation avoids cross-test contamination.

### IV. Docker-First Local Development

- All local development MUST use `docker compose up` with
  `Dockerfile.dev` configurations that bind-mount source for
  live-reload.
- **No bare-metal runs**: Backend, frontend, and scraper services run
  exclusively inside Docker containers. PostgreSQL MUST use the
  `pgvector/pgvector:pg15` image with the pgvector extension.
- **Makefile as interface**: All developer-facing operations (migrate,
  test, scrape, dump/sync, backfill) MUST be accessible via Makefile
  targets that execute inside the appropriate Docker service.
- **Service architecture**: 7 services — `app` (scraper runner),
  `backend` (FastAPI on :8000), `frontend` (Next.js on :3000),
  `postgres` (:5433→5432), `pgadmin` (:886→80), `test_service`
  (one-off pytest), `job_service` (migrations, dump/sync, scrape,
  backfill).

Rationale: Docker-first eliminates "works on my machine" issues and
ensures parity between developer environments and CI service
containers.

### V. CI-Only Deployment Boundary

- **GitHub Actions** performs CI only: lint, test, coverage, and
  auto-migration on push to `master`. It MUST NOT build or deploy
  artifacts.
- **Railway** handles CD: continuous deployment from the `master`
  branch. Railway is the single source of production truth.
- **Migration safety**: On push to master, CI runs
  `alembic upgrade head` against the production DB. If any downstream
  test stage fails, the `rollback` job runs `alembic downgrade -1` on
  production automatically.
- **No direct production access**: Migrations and retries against
  production MUST go through Makefile targets (`make migrate-remote`,
  `make retry-failed-remote`) that use `REMOTE_RAILWAY_DB_URL`.

Rationale: Separating CI from CD prevents accidental production
deployments from PR branches and ensures Railway is the authoritative
deployment pipeline.

### VI. Observability as a First-Class Concern

- **Structured logging**: structlog with Loki transport. All services
  MUST log via structlog, not `print()` or bare `logging`.
- **Tracing**: OpenTelemetry traces to Grafana Cloud. New HTTP
  endpoints and scraper pipeline steps MUST include span creation.
- **Metrics**: OpenTelemetry metrics for scrape volume, LLM usage,
  pipeline timing. `RequestLoggingMiddleware` MUST remain active on
  backend.
- **Error tracking**: Sentry integration MUST be active in production.
  Unhandled exceptions MUST propagate to Sentry; silent swallowing is
  forbidden.
- **Graceful degradation**: All observability components MUST fail
  silently with no-op fallbacks. Missing Sentry/Loki/OTel config MUST
  NOT crash the application.

Rationale: Production debugging depends on traces, metrics, and logs.
No-op fallbacks ensure local development works without observability
infrastructure.

### VII. Code Style & Quality Standards

- **Python**: Follow PEP 8 conventions. Use `uv` for all dependency
  management (`uv sync`, `uv run`, `uv.lock` committed). Pydantic
  schemas for API input/output validation. Alembic migrations numbered
  with descriptive prefixes.
- **TypeScript/React**: Strict mode enabled. ESLint with
  `core-web-vitals` + `typescript` configs. Prettier with 100-char
  width, double quotes, trailing commas, 2-space indent. Shadcn/UI
  primitives MUST NOT be modified directly; extend via composition.
- **ORM conventions**: UUID primary keys on all models. `metadata_`
  Python attribute maps to `metadata` DB column. `User` model lives in
  `auth` PostgreSQL schema. `configure_mappers()` called in
  `tag.py` for circular dependency resolution.
- **i18n**: All user-facing strings MUST use the I18nProvider with
  locale files in `frontend/i18n/`. Server-side translation via
  `TranslateArticleUseCase` and `TranslateTagsUseCase`.
- **No TODO comments in production code**: Either implement the
  feature or create a tracked issue. No placeholder implementations.

Rationale: Consistent style reduces review friction. Committed
`uv.lock` and strict TypeScript prevent dependency drift and runtime
type errors.

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language (Backend) | Python | >=3.11 |
| Language (Frontend) | TypeScript + React | 19.x / strict |
| Package Manager (Python) | uv | 0.10.x |
| Package Manager (Frontend) | npm | lockfile committed |
| Web Framework | FastAPI | >=0.111 |
| Frontend Framework | Next.js | 16.x (App Router) |
| ORM | SQLAlchemy | >=2.0 |
| Database | PostgreSQL + pgvector | 15 |
| Migrations | Alembic | >=1.13 |
| Auth (Frontend) | NextAuth v4 | JWT strategy |
| Auth (Backend) | python-jose | HS256 JWT |
| UI Components | Shadcn/UI + Radix UI + Tailwind CSS v4 | — |
| LLM Providers | Gemini, Claude, OpenRouter | via `providers.toml` |
| Observability | OpenTelemetry, Sentry, Loki, structlog | — |
| Testing (Python) | pytest + pytest-cov + pytest-asyncio | — |
| Testing (Frontend) | Vitest + Playwright + Storybook | — |
| CI | GitHub Actions | — |
| CD | Railway | — |

## Development Workflow

### Branch & PR Conventions

- All work MUST happen on feature branches (`feat/`, `fix/`, `chore/`).
  Never commit directly to `master`.
- PRs targeting `master` trigger the full CI pipeline plus CodeRabbit
  AI review.
- Merge commits on `master` trigger Railway auto-deploy.

### Database Changes

- All schema changes MUST be delivered as Alembic migrations.
- Migrations MUST be tested locally via `make migrate` before push.
- Auto-migration on CI runs against production; rollback job guards
  against downstream failures.

### LLM Provider Configuration

- Provider priority and rate limits are configured in `providers.toml`
  at project root. New providers MUST be added there, not hardcoded.
- `ResilientLLMService` walks providers in priority order with
  `SlidingWindowStrategy` rate limiting. Falls back on
  `RateLimitExhausted` or any exception.

### Frontend API Access

- Frontend MUST NOT call the backend directly. All API requests go
  through the Next.js catch-all reverse proxy at
  `app/api/proxy/[...path]/route.ts`.
- Client code MUST use `apiFetch()` from `lib/api-fetch.ts` which
  prefixes with `/api/proxy` and appends `lang` from localStorage.

### Scraper Pipeline

- Pipeline follows: Discover → Pre-dedup → Fetch → Publish → Process
  → Analyze → Translate → Notify.
- Scheduled runner adds 0-180s random startup jitter (disable with
  `RUN_IMMEDIATELY=1`), has a 50-min hard timeout, and handles
  SIGTERM/SIGINT for graceful shutdown.
- Failed tasks are retried via `make retry-failed` with configurable
  `HOURS` and `LIMIT`.

## Governance

- This constitution supersedes all other development practices and
  conventions for the scrape-and-analyze project.
- Amendments MUST be documented with a version bump, rationale, and
  migration plan if the change affects existing code.
- All PRs and code reviews MUST verify compliance with these
  principles. Complexity that violates principles MUST be justified
  in the Complexity Tracking section of the implementation plan.
- Use `CLAUDE.md` at project root for AI assistant runtime guidance;
  this constitution provides the authoritative principles that CLAUDE.md
  references.

**Version**: 1.0.0 | **Ratified**: 2026-05-28 | **Last Amended**: 2026-05-28
