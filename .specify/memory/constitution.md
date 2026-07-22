<!--
Sync Impact Report:
- Version change: 1.4.0 → 1.5.0 (MINOR: expanded Principle I with a domain-layer
  dataclass-vs-Pydantic rule, formalizing a pre-existing but previously
  undocumented codebase convention discovered during a code review)
- Modified principles:
  - I. Domain-Driven Design: added a sub-bullet under the Domain layer entry
    requiring stdlib `@dataclass` by default for entities/value objects, with
    Pydantic `BaseModel` permitted only for a genuinely Pydantic-specific
    capability (documented exception: `ScraperKeywordVO`'s discriminated union)
- Added sections: None
- Removed sections: None
- Templates requiring updates:
  - .specify/templates/tasks-template.md: ✅ compatible (no dataclass/Pydantic references)
  - .specify/templates/plan-template.md: ✅ compatible
  - .specify/templates/spec-template.md: ✅ compatible
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
  - Entities and value objects MUST default to stdlib `@dataclass`.
    Pydantic `BaseModel` MUST NOT be used in the domain layer unless a
    genuinely Pydantic-specific capability is required and a `@dataclass`
    cannot reasonably provide it (documented exception: `ScraperKeywordVO`
    in `src/modules/collection/domain/value_objects/scraper_keyword.py`,
    which needs `Field(discriminator="type")` for polymorphic
    deserialization). Pydantic remains reserved for API/config boundaries
    per Principle VII, not as a default choice for domain modeling.
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

Component reuse and documentation rules:

- **Reuse first**: Before creating a new component, existing components
  in `components/ui/`, `components/common/`, and `components/features/`
  MUST be evaluated for reuse or composition. New components MUST only
  be introduced when no existing component can reasonably satisfy the
  requirement.
- **Storybook story required**: Every new component added to
  `components/common/` or `components/features/` MUST ship with a
  corresponding Storybook story (`.stories.tsx`) in the same directory.
  Stories MUST cover at minimum the default state and any significant
  variants or interactive states. Shadcn/UI primitives in
  `components/ui/` are exempt from this rule.

Rationale: Clear component boundaries prevent feature coupling and keep
UI primitives reusable across admin and public routes. Mandatory
Storybook stories ensure new shared components are discoverable and
visually verified before integration.

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
- **Docker-only test execution**: All test runs MUST be executed inside
  Docker containers via Makefile targets (`make test` for unit,
  `make test-integration` for integration). Running pytest directly on
  the host (`uv run pytest`) is permitted only for IDE test discovery;
  CI and all acceptance runs MUST use Docker.
- **CI gates**: Unit tests run first; integration/E2E only after unit
  pass. Coverage uploaded to Codecov with carryforward.
- **Mandatory test tasks in every tasks.md**: Every feature
  implementation MUST include at least one dedicated test phase in
  `tasks.md`. Tests are NOT optional and MUST NOT be omitted even if
  not explicitly requested in the spec. The test phase MUST use the
  project's established test directories and frameworks:
  - Frontend unit tests → `frontend/tests/unit/` (Vitest)
  - Frontend E2E tests → `frontend/tests/integration/` (Playwright)
  - Backend unit tests → `backend/tests/` (pytest)
  - Scraper unit tests → `src/tests/unit/` (pytest)
  - Scraper integration tests → `src/tests/integration/` (pytest,
    `@pytest.mark.integration`)
  The tasks template instruction "Tests are OPTIONAL" does NOT apply
  to this project. `speckit-tasks` MUST always generate test tasks.

Rationale: Isolated, deterministic tests prevent flaky CI and ensure
fast feedback loops. Schema isolation avoids cross-test contamination.
Mandatory test tasks in every feature prevent the recurring gap where
implementation is complete but automated coverage is absent.

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
- **Service architecture**: 10 services across two tiers.
  Always-on (`docker compose up`): `postgres` (:5432), `redis`
  (:6379), `pgadmin` (:80), `backend` (FastAPI :8000), `frontend`
  (Next.js :3000), `fastembed` (ONNX embedding server :8080),
  `chatbot_plugin` (RAG chat API :8001). One-off tools (started
  via `docker compose run`, never via `docker compose up`): `app`
  (scraper runner), `test_service` (pytest), `job_service`
  (migrations, dump/sync, backfill).
- **Docker Compose profiles**: One-off services MUST carry
  `profiles: ["tools"]`. `docker compose up` MUST NOT start tool
  containers. `docker compose run --rm <service> <cmd>` works
  without `--profile tools`.

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

- **Structured logging**: All services MUST emit structured JSON logs
  to stdout and optionally ship to Loki. The scraper (`src/`) uses
  structlog; FastAPI microservices (`backend/`, `chatbot-plugin/`,
  `services/fastembed/`) use stdlib `logging` with a `_JsonFormatter`
  producing `{"event", "level", "logger", "service", "timestamp"}`
  output compatible with scraper's structlog format. `print()` and
  unformatted `logging.basicConfig()` are forbidden in all services.
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

### VIII. UML Architecture Diagram Conventions

The pipeline and class diagram at `site/guide/architecture/uml` is auto-generated by
`scripts/generate_uml.py`. The script infers topology purely from code structure — no
manual configuration is required. The following conventions MUST be followed for
auto-generation to remain correct.

**Directory Structure** (drives layer and context classification):

- Business modules MUST live under `src/modules/<module_name>/`. Adding a new directory
  here automatically adds a context tab in the UML viewer.
- Infrastructure implementations MUST live under `src/infrastructure/<module_name>/`.
- Composition root MUST be `src/bootstrap.py`. This file is scanned to infer the
  entire pipeline flow.
- Module sub-directories MUST follow standard DDD layers:
  `domain/entities/`, `domain/repositories/`, `domain/value_objects/`,
  `domain/services/`, `domain/events/`, `application/use_cases/`,
  `application/event_handlers/`, `application/dtos/`, `application/ports/`.

**Event Naming**:

- All domain event classes MUST end in `Event` (e.g., `ArticleScrapedEvent`).
  The DI tree excludes classes ending in `Event` to avoid polluting dependency graphs.
- Failure/error events MUST contain `Failed` in the class name
  (e.g., `AnalysisFailedEvent`). The pipeline viewer uses this keyword to identify
  branch/error paths and render them separately from the main chain.

**Handler Interface**:

- Handler classes MUST be `UpperCamelCase`.
- Handlers MUST expose a `handle()` method — this is the method scanned for
  `*.publish(...)` calls to infer which events each handler emits.
- Handlers MUST be wired in `bootstrap.py` via:
  `event_bus.subscribe(SomeEvent, handler.handle)`.
  The pipeline builder function is auto-detected as the function in `bootstrap.py`
  with the most `subscribe()` calls — no function name needs to be hardcoded.

**Event Publishing**:

- Events MUST be published via `*.publish(SomeEvent(...))` inside `handle()` methods.
- The topology inference classifies entry events as "main chain" (handlers that publish
  further events) vs "terminal" (handlers that only notify/log with no further publishing).
  This drives the two-phase BFS ordering of the pipeline diagram.

**Pipeline and Repository Naming**:

- The primary pipeline class MUST contain `Pipeline` in its name but NOT `Stats`
  (e.g., `CollectionPipeline` is fine; `PipelineStats` is excluded).
- Repository implementation classes MUST have filenames ending in `_repo_impl`
  (e.g., `article_repo_impl.py`) for correct `infrastructure-persistence` layer
  classification.

Running `make uml-backend` regenerates the diagram after any code change. No
configuration files need to be edited when adding new handlers, events, or modules —
as long as these conventions are followed.

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
- **VitePress-compatible Markdown**: All spec and documentation
  markdown files rendered via VitePress MUST avoid bare angle-bracket
  syntax outside of fenced code blocks. Generic type expressions
  (e.g., `Array<T>`, `Record<K, V>`) and placeholder tokens
  (e.g., `<ISO_8601>`, `<UUID>`) MUST be wrapped in backticks or
  escaped as `&lt;`/`&gt;`. Vue's production compiler (`npm run build`)
  is stricter than the dev-server runtime — bare `<…>` outside code
  blocks is treated as an unclosed HTML element and fails the build
  even if `npm run dev` renders correctly.

Rationale: Consistent style reduces review friction. Committed
`uv.lock` and strict TypeScript prevent dependency drift and runtime
type errors.

### IX. FastAPI Microservice Structure

Each Python microservice (`backend/`, `chatbot-plugin/`,
`services/fastembed/`) MUST follow this layout:

- **`config.py`** — All `os.environ.get()` reads in one place. Pure
  reads only; no side effects, no imports from the rest of the
  package. Every other module imports from here — no `os.environ`
  calls elsewhere in the service.
- **`observability.py`** — Exports
  `configure_logging(service, loki_url, loki_user, loki_api_key, app_env)`.
  Installs a JSON stdout handler and optionally a Loki handler.
  Called once at module top-level in `main.py`, before any logger is
  used.
- **`routers/__init__.py`** — Imports and re-exports router objects
  to a single name (e.g. `api_router`, `embed_router`).
- **`routers/<name>.py`** — Route handlers only. Reads services from
  `request.app.state`; imports config from `config`. Zero business
  logic.
- **`services/__init__.py`** — Empty.
- **`services/<name>.py`** — Service class with injected
  dependencies; async/sync business logic methods. No knowledge of
  HTTP or config.
- **`main.py`** — Thin entry point: calls `configure_logging()`,
  defines `lifespan` (builds dependencies → assigns to `app.state` →
  yields → teardown), creates `FastAPI(lifespan=lifespan)`, calls
  `app.include_router(...)`.

**Environment variable discipline**: All env vars MUST appear in
`.env.example` (the Railway shared-variable source of truth).
Hardcoded values in `docker-compose.yml` `environment:` blocks are
forbidden; always use `env_file: .env` and declare defaults only in
`config.py`.

**Log format** (all microservices, compatible with scraper structlog):

```json
{"event": "...", "level": "info", "logger": "...", "service": "...", "timestamp": "..."}
```

Rationale: Consistent structure across services reduces onboarding
friction and ensures Loki/Grafana queries work identically whether
targeting the scraper, backend, or embedding service.

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

**Version**: 1.5.0 | **Ratified**: 2026-05-28 | **Last Amended**: 2026-07-21
