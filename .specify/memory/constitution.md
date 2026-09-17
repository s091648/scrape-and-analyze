<!--
Sync Impact Report:
- Version change: 1.8.0 → 1.9.0 (MINOR: seven new principles distilled from
  specs 016-026, which had accumulated project-wide, non-negotiable rules
  never propagated back into the constitution; one existing principle
  amended with an additive bullet; two stale references to the retired
  providers.toml LLM config corrected to the current DB-driven design.)
- Modified principles:
  - I. Added a bullet requiring the shared `DbSchema` enum for every
    model's schema assignment (016-db-schema-brushup), instead of a
    hardcoded string literal — a DB-layer manifestation of the existing
    DDD/bounded-context principle.
  - IX. Environment-variable-discipline paragraph now points to the new
    Principle XII instead of restating a now-outdated, narrower version
    of the same rule.
- Added principles:
  - X. Centralized Exception Handling (017-exception-handling-guideline)
  - XI. Public API Authentication Floor (018-public-api-auth)
  - XII. Environment Variable Discipline (016-db-schema-brushup,
    025-iac-provisioning)
  - XIII. Fail-Open Auxiliary Infrastructure (020-redis-caching-layer,
    026-rate-limit-codegen)
  - XIV. Generated Artifact Integrity (016-db-schema-brushup,
    026-rate-limit-codegen; generalizes the existing UML-specific
    Principle VIII)
  - XV. Infrastructure & Secrets Management (025-iac-provisioning)
  - XVI. Infrastructure Minimalism (020-redis-caching-layer,
    023-article-search)
- Corrected (non-semantic): Technology Stack table's "LLM Providers" row
  and the "LLM Provider Configuration" Development Workflow section both
  referenced the retired `providers.toml`; both now describe the current
  DB-driven `llm_providers` table design.
- Removed sections: None
- Templates requiring updates:
  - .specify/templates/tasks-template.md: ✅ compatible (no principle-specific references)
  - .specify/templates/plan-template.md: ✅ compatible (Constitution Check gate is generic)
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
- **Schema assignment**: Every SQLAlchemy model MUST declare its
  PostgreSQL schema via the shared `DbSchema` enum (`models/db_schema.py`)
  in `__table_args__`, never a hardcoded schema string literal — the
  bounded-context-to-schema mapping stays in one place the diagram
  generator can also read from.

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

### V. Explicit CI/CD Deployment Boundary

- **GitHub Actions performs both CI and explicit CD** via the Railway
  CLI (`railway up --detach --service <id>`) — it is not CI-only.
  Deploys are gated on tests passing and only fire on two specific
  triggers, never on a bare merge to `master`:
  - **Staging** (`.github/workflows/ci.yml`, `deploy-staging-*` jobs):
    fires only on `pull_request` events, after the relevant test jobs
    succeed. Deploys the PR's checked-out commit to each service's
    Railway *staging* environment.
  - **Production** (`.github/workflows/release.yml`): fires only on
    pushing a `v*` tag, after stamping the version and running
    `alembic upgrade head` against production. Deploys every service
    to Railway *production*.
  - A plain push to `master` (post-merge) runs migration + tests +
    the `rollback` safety net only — it does not deploy anything.
- **Exception — `chatbot-plugin`**: this service has its own standalone
  GitHub repo (`github.com/s091648/chatbot-plugin`), own CI
  (`chatbot-plugin/.github/workflows/ci.yml`, gated by that repo's own
  branch protection on `master`), and own semver `v*` release tags
  (`chatbot-plugin/.github/workflows/release.yml`). Railway's native
  Git integration for this service is intentionally NOT connected —
  it is deployed only via this monorepo's `railway up` calls, using
  whatever commit the `chatbot-plugin` submodule pointer has checked
  out. The two monorepo triggers apply asymmetrically to it:
  - **Staging** deploys the submodule pointer's current commit as-is,
    tagged or not — staging is a preview environment, not a release.
  - **Production** deploys it only if that exact commit carries a `v*`
    tag in `chatbot-plugin`'s own repo (verified by `release.yml`
    before the `railway up` call); an untagged commit is skipped with
    a loud warning rather than silently deployed. This mirrors a
    build-once/tag-then-promote pattern (the `chatbot-plugin` repo is
    the "build once, test, tag" stage; this monorepo just pins and
    promotes an already-tagged reference to production) without
    needing a container registry.
- **Migration safety**: On push to master, CI runs
  `alembic upgrade head` against the production DB. If any downstream
  test stage fails, the `rollback` job runs `alembic downgrade -1` on
  production automatically.
- **Data migrations run alongside schema migrations**: Immediately after
  each `alembic upgrade head` step in `ci.yml`'s `migrate` job (staging)
  and `release.yml` (production), a second step runs
  `scripts/run_data_migrations.py` to apply any pending standalone data
  migration from `scripts/data/versions/` (the `data_migrations`-table-
  tracked, Alembic-analogous framework for one-off data fixes that aren't
  tied to a schema change). It is deliberately not run against the three
  ephemeral-per-job test databases. `requires_api=True` migrations are
  always skipped by these automatic runs (manual-only, via
  `make data-migrate --include-api`). A migration's `up()` runs in its own
  transaction; on failure it rolls back, is not recorded, halts the rest
  of that run's chain, and fails the containing CI job — without
  reversing an already-successful schema migration from the same run.
- **No direct production access**: Migrations and retries against
  production MUST go through Makefile targets (`make migrate-remote`,
  `make retry-failed-remote`) that use `REMOTE_RAILWAY_DB_URL`.

Rationale: Gating deploys on explicit CI triggers (PR review for
staging, version tags for production) instead of Railway's own
branch-watching auto-deploy prevents unreviewed or untested commits
from reaching a live environment. `chatbot-plugin` previously also had
Railway's own Git integration watching its standalone repo directly,
deploying on every push independent of (and untested by) either repo's
CI — that auto-deploy has been removed in favor of the tag-gated
promotion described above, so a production deploy of that service now
always traces back to a commit that passed its own CI and was
deliberately released.

### VI. Observability as a First-Class Concern

- **Structured logging**: All services MUST emit structured JSON logs
  to stdout and optionally ship to Loki. The scraper (`src/`) uses
  structlog; FastAPI microservices (`backend/`, `chatbot-plugin/`,
  `fastembed/`) use stdlib `logging` with a `_JsonFormatter`
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
`fastembed/`) MUST follow this layout:

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

**Environment variable discipline**: See Principle XII for the full,
CI-enforced rule (one centralized module per service, no direct
`os.environ` elsewhere). All env vars MUST also appear in `.env.example`
(the Railway shared-variable source of truth); hardcoded values in
`docker-compose.yml` `environment:` blocks are forbidden — always use
`env_file: .env` and declare defaults only in `config.py`.

**Log format** (all microservices, compatible with scraper structlog):

```json
{"event": "...", "level": "info", "logger": "...", "service": "...", "timestamp": "..."}
```

Rationale: Consistent structure across services reduces onboarding
friction and ensures Loki/Grafana queries work identically whether
targeting the scraper, backend, or embedding service.

### X. Centralized Exception Handling

- Every exception that reaches an HTTP API boundary MUST resolve to a
  status code through exactly one central `DomainError`→HTTP-status
  mapping (`backend/exceptions/handlers.py`); routers MUST NOT construct
  `HTTPException` directly, with one documented exception (`chat.py`'s
  429 rate-limit response, since 429 predates the `DomainError` category
  mapping).
- Every domain exception raised anywhere in `src/`/`backend/` MUST
  subclass `DomainError` (`shared/domain/exceptions.py`) via one of its
  shared categories (`ValidationError`, `NotFoundError`, `ConflictError`,
  `UnauthorizedError`, `ForbiddenError`, `ExternalDependencyError`) — a
  new bounded-context root or leaf exception MUST fit into this hierarchy
  rather than raising a bare built-in exception (`ValueError`,
  `Exception`) at an API-facing layer.
- Authentication/authorization guards MUST raise a shared domain
  exception rather than constructing their own `HTTPException` — they go
  through the same central mapping as every other domain exception, not
  a parallel bypass path.
- Any exception reaching the API boundary with no explicit entry in the
  mapping MUST default to HTTP 500, so an unmapped exception never
  surfaces an inconsistent or undefined status code.
- This requirement applies only to code paths that terminate in an HTTP
  response; background/async pipeline code (the scheduled scraper,
  periodic view-count flush) keeps using the same domain exception
  hierarchy for consistency but has no status-code mapping to satisfy.

Rationale: Before this was codified, authentication guards bypassed the
domain exception hierarchy by raising `HTTPException` directly, producing
two parallel error paths that could silently diverge
(specs/017-exception-handling-guideline). A single mapping keeps error
responses consistent and auditable regardless of which layer raised the
failure.

### XI. Public API Authentication Floor

- Every backend endpoint MUST require at least `require_any_token` (a
  valid guest-or-real JWT) unless it is one of the small, explicitly
  documented exceptions: the guest-token bootstrap itself
  (`POST /auth/guest`, `POST /auth/guest/refresh`) and any endpoint
  already gated by a stronger requirement (`require_user`,
  `require_admin`). "Fully public, zero authentication" MUST NOT be a
  state a new endpoint can silently launch in.
- A guest access token grants no access beyond "has a valid token" — it
  MUST continue to be refused by every endpoint that requires a specific
  logged-in user or `admin` role, with no new permission tier introduced
  by the existence of guest tokens.
- Guest tokens MUST remain stateless (self-signed JWTs verified through
  the same signing/verification path as real login tokens,
  `backend/auth/guards.py`) — no new DB-backed session table or
  per-guest revocation mechanism.

Rationale: This closes a real gap where public-looking endpoints had no
auth check at all, letting any external consumer bypass the frontend
entirely (specs/018-public-api-auth). Defaulting new endpoints to the
`require_any_token` floor, rather than defaulting to public, keeps that
gap from reopening as the API surface grows.

### XII. Environment Variable Discipline

- Every Python service (`backend/`, `chatbot-plugin/`, `fastembed/`, and
  the scraper's shared `src/`) MUST read every environment variable
  exactly once, through that service's own centralized config/settings
  module. No other module in that service's runtime code path —
  including its own shared utility modules — may call `os.environ`
  directly.
- Shared utility code (e.g. `shared/`) MUST NOT read environment
  variables itself, even when only one service currently calls it; it
  MUST receive the value as an explicit parameter from the calling
  service's centralized config.
- The frontend MUST route all environment access through a centralized
  module split into a server-only file (full `process.env`, for Server
  Components/Route Handlers) and a client-safe file (`NEXT_PUBLIC_*`
  only, for Client Components). Client Components MUST NOT call
  `process.env` directly outside the client-safe module.
- Where a value must be read fresh rather than import-time-frozen (e.g.
  for test observability), the centralized module MUST expose an
  explicit re-readable accessor — a direct `os.environ`/`process.env`
  call outside the module is never an acceptable substitute, including
  for test convenience.
- An automated CI check (lint rule or repo-wide grep) MUST catch a direct
  `os.environ`/`process.env` call added outside the designated modules.
  Documentation alone is insufficient — this rule has already eroded
  once and been re-established (specs/016-db-schema-brushup,
  specs/025-iac-provisioning).

Rationale: A single centralized module per service makes every
environment dependency discoverable in one place and testable without
monkeypatching scattered call sites. CI enforcement exists because the
convention silently eroded under documentation alone before 025
re-established it — a rule with no automated check is not a rule future
contributors can be expected to remember.

### XIII. Fail-Open Auxiliary Infrastructure

- Auxiliary infrastructure that accelerates or protects the system —
  caching (Redis) and rate limiting — MUST fail open: if the backing
  store is unavailable, requests MUST still succeed (cache: fall back to
  the database; rate limiting: allow the request through) rather than
  fail the request.
- Bounded TTLs are the accepted backstop against a missed cache
  invalidation, not a reason to fail closed instead.
- This does not apply to infrastructure that is itself the primary
  guarantee being requested (e.g. a payment or auth check) — only to
  auxiliary systems whose unavailability should degrade performance or
  throttling, never core functionality.

Rationale: An outage in a caching or rate-limiting store must never
become an outage of the product itself — availability of the core
feature always outranks the auxiliary concern it's paired with
(specs/020-redis-caching-layer, specs/026-rate-limit-codegen).

### XIV. Generated Artifact Integrity

- Any artifact auto-generated from source code (the UML pipeline/class
  diagram, the DB schema diagram, the exception catalog, frontend API
  types generated from the backend OpenAPI contract) MUST hard-fail its
  generation step if it cannot fully and correctly represent its source
  — a partial or best-effort artifact MUST NOT be silently produced.
- Any consumer of a generated artifact that can drift out of sync with
  its source (e.g. frontend API types vs. the backend OpenAPI contract)
  MUST have an automated CI check that fails when the artifact is stale,
  rather than relying on reviewer diligence to notice.
- See Principle VIII for the concrete, currently most-detailed instance
  of this pattern (the UML diagram generator's code-structure
  conventions).

Rationale: This pattern has recurred across three separate features (UML
diagrams, the DB schema diagram, generated frontend API types) — each
time because a stale or silently-wrong generated artifact is worse than
no artifact, since it actively misleads. Codifying the general rule here
means the next generated artifact inherits the same guarantee without
waiting for its own incident.

### XV. Infrastructure & Secrets Management

- A secret value (API key, database URL, token) MUST NOT be stored in
  plaintext in any version-controlled file, pull request diff, or CI
  log.
- The IaC tool's applied-state record — which necessarily contains
  plaintext secret values once a secret has been applied — MUST be
  stored in a remote backend that is encrypted at rest and
  access-restricted to the CI/CD pipeline and maintainer, never
  committed to the repository.
- Secret values MUST continue to originate from the GitHub Actions
  secrets store and be injected into the apply step at run time, not
  authored directly into declarative infrastructure files — GitHub
  Actions secrets remain the single source of truth for what a secret's
  value *is*; the IaC tool is only responsible for applying it.
- Railway's own managed database services (Redis, Postgres) remain
  manually provisioned and stay outside the declarative infrastructure
  definition's scope — only the app-service variables that reference
  them are declared.
- The bootstrap credentials that authenticate the IaC tool to its own
  state backend, GitHub, and Railway MUST be the only standing manual
  exceptions to full declarative management, and MUST be documented as
  such wherever the infrastructure is defined.

Rationale: Infrastructure-as-code that leaks the secrets it manages, or
that hides an unencrypted copy of every secret in its own state file,
defeats the point of moving secrets out of ad-hoc scripts in the first
place (specs/025-iac-provisioning).

### XVI. Infrastructure Minimalism

- A new feature requiring backend capability MUST first evaluate whether
  already-deployed infrastructure can satisfy it before introducing a
  new infrastructure dependency or service.
- Deviating from this default (adding a new datastore, search engine, or
  external service) MUST be justified in the plan's Complexity Tracking
  section — reuse is the default, not one option among equals.

Rationale: Two independent features chose to extend existing
infrastructure (pgvector, already populated for embeddings) over
standing up a new one (a dedicated search engine) purely because the
reuse path was available and sufficient (specs/020-redis-caching-layer,
specs/023-article-search). Stating this as a default keeps that judgment
call consistent across future features instead of re-litigating it each
time.

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
| LLM Providers | Gemini, Claude, OpenRouter | DB-driven (`llm_providers` table) |
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

- Provider priority, rate limits, and model config are DB-driven via the
  `llm_providers` table (`models/llm_provider.py`), not a config file —
  new providers MUST be added as rows (via the admin
  `/admin/llm-providers` dashboard or a migration), not hardcoded.
- `ResilientLLMService`/`AsyncResilientLLMService` walk providers in
  priority order with `SlidingWindowStrategy` rate limiting. Falls back
  on `RateLimitExhausted` or any exception.

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

**Version**: 1.9.0 | **Ratified**: 2026-05-28 | **Last Amended**: 2026-09-16
