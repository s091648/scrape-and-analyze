# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend / Scraper (Python)

| Command | Purpose |
|---|---|
| `make test` | Run unit tests (`src/tests/unit/`) via Docker |
| `make test-cov` | Unit tests with HTML coverage (`src/tests/htmlcov/`) |
| `make test-integration` | Integration tests (requires local postgres) |
| `make test-integration-cov` | Integration tests with coverage |
| `make test-all-cov` | All tests with combined HTML coverage |
| `make scrape SOURCE=rss` | Manual scrape; supports `LIMIT=`, `DAYS_BACK=`, `NO_ANALYZE=1` |
| `make run` | Run the scheduled scraper pipeline |
| `make migrate` | Run `alembic upgrade head` locally |
| `make migrate-remote` | Run migrations against production DB (needs `REMOTE_RAILWAY_DB_URL` in `.env`) |
| `make migrate-down` | Rollback one migration (override with `DOWNGRADE_REV=<rev>`) |
| `make migrate-remote-down` | Rollback on production DB |
| `make dump` / `make sync` | Dump remote DB / restore to local postgres |
| `make create-admin` | Create an admin user interactively |
| `make retry-failed` | Retry failed tasks; supports `HOURS=`, `LIMIT=` |
| `make retry-failed-remote` | Retry failed tasks against production DB |
| `make backfill` | Backfill tags; supports `LIMIT=` |
| `make backfill-dry-run` | Dry-run tag backfill |
| `make translate LANG=zh-TW` | Translate article analyses; supports `LIMIT=` |
| `make pg_init` | Stamp legacy DB with alembic baseline (one-time, for DBs without alembic_version) |

Run a single test file: `uv run pytest src/tests/unit/test_foo.py`
Run a single test: `uv run pytest src/tests/unit/test_foo.py::test_bar -v`
Run backend tests: `uv run pytest backend/tests/`
Run script tests: `uv run pytest scripts/tests/`

### Frontend

| Command | Purpose |
|---|---|
| `cd frontend && npm run dev` | Next.js dev server (port 3000) |
| `cd frontend && npm run test` | Vitest unit tests |
| `cd frontend && npm run test:watch` | Vitest in watch mode |
| `cd frontend && npm run test:coverage` | Vitest with coverage |
| `cd frontend && npm run test:e2e` | Playwright E2E tests |
| `cd frontend && npm run lint` | ESLint |
| `cd frontend && npm run format` | Prettier |

### Docker

`docker compose up` — starts postgres (5432), backend (8000), frontend (3000), pgadmin (80), scraper app.

Docker services: `app` (scraper runner, sleeps until invoked), `backend`, `frontend`, `postgres`, `pgadmin`, `test_service` (for pytest via `make test`), `job_service` (for one-off jobs: migrations, dump/sync, scrape, backfill). All mount source dirs for live-reload.

## Architecture

Three services sharing one PostgreSQL database:

- **`src/`** — Scraper/analyzer service (domain logic, scheduled scraping, LLM analysis, notifications)
- **`backend/`** — FastAPI REST API (port 8000) serving the frontend
- **`frontend/`** — Next.js 16 + React 19 web UI (port 3000)
- **`models/`** — Shared SQLAlchemy ORM models used by both `src/` and `backend/`

### API Proxy Pattern

The frontend does **not** call the backend directly. All API requests go through a Next.js catch-all reverse proxy at `frontend/app/api/proxy/[...path]/route.ts`, which forwards to `http://backend:8000`. Client code uses `apiFetch()` from `frontend/lib/api-fetch.ts` which prefixes paths with `/api/proxy` and appends `lang` from localStorage.

### Auth Flow

NextAuth v4 (JWT strategy) on frontend → `jose` signs HS256 JWT with `sub` (user ID) and `role` → JWT passed as `Authorization: Bearer` through proxy → `backend/auth/guards.py` validates with `NEXTAUTH_SECRET` and enforces `require_admin` / `require_user` via `Depends()`. Two Google providers: `google-login` (existing users) and `google-register` (new sign-ups).

### Frontend Layout

Root layout wraps: `SessionProviderWrapper > TopicProvider > I18nProvider > ErrorBoundary > NavBar`. State uses React Context (`TopicContext` with localStorage persistence) — Zustand is a dependency but no stores exist yet. Routes: `/` (home), `/graph` (force-graph), `/login`, `/register`, `/settings`, `/admin/*` (monitoring, scraper-settings, topics, user-management).

**`page.tsx` vs `xxx-page-content.tsx` split** — a route's `page.tsx` stays a thin wrapper (import + return only) and the real component moves to a sibling `xxx-page-content.tsx` file whenever either applies:
- The page reads `useSearchParams()` (or another hook requiring a Suspense boundary) — `page.tsx` wraps `<XxxPageContent />` in `<Suspense>`. See `app/login/`, `app/register/`, `app/settings/`, `app/settings/notifications/`, `app/articles/`, `app/page.tsx`.
- The page needs server-only data (`getServerSession`, non-`NEXT_PUBLIC_` env vars) before the client component renders — `page.tsx` is an `async` server component that fetches the data and passes it as props. See `app/admin/monitoring/`.

Routes needing neither (no `useSearchParams`, no server-only session/env fetch) stay a single-file `page.tsx` — don't split for its own sake (e.g. `app/admin/llm-providers/`, `app/admin/scraper-settings/`, `app/graph/`, `app/tags/`).

### Backend Routers

| Router | Prefix | Auth |
|---|---|---|
| `articles.py` | `/` | `require_any_token` (any valid token — guest or logged-in); `POST /admin/articles/flush-view-counts` require_admin |
| `auth.py` | `/auth` | Admin on user mgmt; `require_user` on `/me`; `POST /guest` and `POST /guest/refresh` unauthenticated (the guest-token bootstrap itself) |
| `graph.py` | `/` | `require_any_token` |
| `scraper_settings.py` | `/scraper-settings` | All require_admin |
| `topics.py` | `/topics` | `GET` requires `require_any_token`; write ops require_admin |
| `scraper_keywords.py` | `/scraper-keywords` | All require_admin |
| `languages.py` | `/api` | `require_any_token` (resolves language from client IP via GeoIP) |
| `llm_providers.py` | `/llm-providers` | All require_admin |
| `metric_definitions.py` | `/` | `GET /metric-definitions` public; `/admin/metric-definitions` (GET, PATCH) require_admin |
| `weekly_reports.py` | `/weekly-reports` | `require_any_token` |
| `tags.py` | `/` | `GET /tag-groups`, `GET /tag-groups/{group_id}` require_any_token; all other (write) endpoints require_admin |
| `chat.py` | `/chat` | `require_any_token` on `/chat/completions` and `/chat/quota` |
| `monitoring.py` | `/` | `GET /failed-tasks` require_admin |

`require_any_token` (`backend/auth/guards.py`, `018-public-api-auth`) accepts any real user/admin JWT or a guest access token (obtained via `POST /auth/guest`, no credentials required); it never accepts a guest *refresh* token. It is the floor auth requirement for every endpoint above that isn't already gated by `require_admin`/`require_user` — see `site/guide/architecture/exception-handling.md`'s sibling doc for the full guest-token contract in `specs/018-public-api-auth/contracts/guest-token.md`.

### Scraper Architecture (Hexagonal / DDD)

`src/` follows domain-driven design:

- **Domain layer** (`src/modules/*/domain/`) — Entities (`Article`, `Analysis`, `ScrapeJob`, `FailedTask`, `Topic`), value objects, repository interfaces, domain service interfaces (`Scraper`, `LLMService`)
- **Application layer** (`src/modules/*/application/`) — Use cases (`ProcessScrapedArticleUseCase`, `AnalyzeArticleUseCase`, `TranslateArticleUseCase`, `TranslateTagsUseCase`), event handlers, DTOs
- **Infrastructure layer** (`src/infrastructure/`) — Concrete implementations: scrapers (`RssScraper`, `BlogScraper`, `ArxivScraper` extending `BaseScraper`), LLM providers (`GeminiProvider`, `ClaudeProvider`, `OpenRouterProvider`), repositories, parsers, notifications, observability

Assembly is in `src/bootstrap.py`: `build_collection_pipeline()` wires the full scrape→analyze→translate pipeline; `build_translation_pipeline()` wires standalone translation.

### Scraper Pipeline Flow

1. **Discover** — Each scraper's `discover()` returns `List[ScrapeJob]` from RSS feeds, blog listings, or ArXiv API
2. **Pre-dedup** — Filter out URLs already analyzed (via `UrlHash`)
3. **Fetch** — `ScrapeExecutor` runs concurrent fetches (5 workers, per-host semaphore, robots.txt respect for blogs)
4. **Publish** — Scraped articles published as `ArticleScrapedEvent` on `InMemoryEventBus`
5. **Process** — `ArticleScrapedHandler` → `ProcessScrapedArticleUseCase` (dedup + save)
6. **Analyze** — `ArticleProcessedHandler` → `AnalyzeArticleUseCase` (LLM chain)
7. **Translate** — `AnalysisCompletedHandler` auto-triggers translation for configured languages
8. **Notify** — `PipelineCompletedEvent` triggers Telegram notifications and OTel metrics

The scheduled runner (`src/entrypoints/cli/main.py`) adds 0-180s random startup jitter (disable with `RUN_IMMEDIATELY=1`), has a 50-min hard timeout, and handles SIGTERM/SIGINT for graceful shutdown.

### LLM Provider Chain

`ResilientLLMService` holds an ordered list of `ProviderHandler` objects (sorted by priority). Each pairs a provider with a `SlidingWindowStrategy` rate limiter (rpm/tpm/rpd). On `analyze()`, walks providers in priority order; falls back on `RateLimitExhausted` or any exception.

**Provider config is DB-driven, not a TOML file** — there is no `providers.toml` in this repo; a prior file-based config was superseded by the `llm_providers` table (`models/llm_provider.py`) in migration `16_add_llm_providers.py`. `shared/llm_provider.py::load_active_providers()` / `load_active_embedding_providers()` / `load_active_multimodal_provider()` load active rows filtered by `type` (`'llm'` / `'embedding'` / `'multimodal'`) and `is_active=True`, ordered by `priority`; `src/bootstrap.py::build_llm_service()` and the weekly-report image pipeline consume these directly from the DB on every run — no config file, no redeploy needed to change a provider, model, or priority. Managed at runtime via `backend/routers/llm_providers.py` (full CRUD + `/reorder`, all `require_admin`) and the `/admin/llm-providers` dashboard page.

### Metric Provider Chain

Same shape as the LLM Provider Chain (a `ResilientMetricsService` walks providers in priority order, `src/infrastructure/collection/metrics/resilient_metrics_service.py`), but the *reason* for multiple providers per metric is different: LLM providers are interchangeable (any of them can generate text, so priority is a pure rate-limit fallback), while metric providers are **not** interchangeable — `OpenAlexClient`/`SemanticScholarClient` each only know how to query their own external citation database via their own identifier scheme. `priority` instead orders which provider to try when an article's available identifiers (DOI and/or arXiv ID) and cross-database coverage make more than one *possibly* able to answer.

Two tables, split 2026-07-12 so the admin-facing and maintainer-only concerns don't leak into each other:
- **`metric_definitions`** (`models/metric_definition.py`) — one row per `metric_key` (e.g. `citation_count`). Display config (`label_i18n_key`, `icon_name`, `format_hint`, `unit`) + `enabled`. `icon_name` and `enabled` are the *only* admin-editable fields, via `PATCH /admin/metric-definitions/{id}` (`backend/routers/metric_definitions.py`) and the `/admin/metric-definitions` dashboard page; `icon_name` is validated server-side against a whitelist mirrored in `backend/schemas/metric_definition.py` (`ICON_WHITELIST`) and `frontend/components/features/articles/metric-icons.ts` (`METRIC_ICON_NAMES`) — keep both in sync when adding an icon.
- **`metric_providers`** (`models/metric_provider.py`) — one row per `(metric_key, provider_name)`. Extraction config only (`provider_name`, `priority`, `extractor_type`, `extractor_spec`) — maintainer-only, migration + code review, never admin-editable. `extractor_type='json_path'` is declarative (a JMESPath string evaluated by `JsonPathMetricExtractor` — safe to store as data, never executable code); `extractor_type='code'` selects a named entry from a fixed in-code registry.

`shared/metric_definition.py::load_enabled_metric_definitions()` joins both tables (filtered to `metric_definitions.enabled=True`) into the flat shape `ResilientMetricsService` expects. Walked by `src/entrypoints/cli/refresh_metrics.py` (recurring cron, keeps `article_metric_values` fresh for articles with a DOI and/or arXiv ID) — independent of the opportunistic free-seed at scrape time (`ProcessScrapedArticleUseCase` forwarding `ScrapedArticle.metric_seeds`, which bypasses this abstraction entirely, no HTTP call). Note: OpenAlex has no arXiv-ID lookup (DOI/PMID/PMCID/MAG ID only); Semantic Scholar does (`paper/ARXIV:<id>`) — `semantic_scholar_arxiv` is a separate `metric_providers` row from `semantic_scholar` (DOI-based) for exactly this reason.

### ORM Models

All models in `models/` use UUID primary keys and share a single `Base = declarative_base()`.

- `User` lives in the `auth` PostgreSQL schema (`__table_args__ = {'schema': 'auth'}`)
- The other 24 tables are organized into 5 PostgreSQL schemas mirroring the DDD bounded contexts in `src/modules/`: `core` (shared kernel), `collection`, `intelligence`, `ai_infra`, `user_prefs` — see `models/db_schema.py`'s `DbSchema` enum (referenced from every model's `__table_args__`) and the auto-generated diagram at `site/guide/architecture/db-schema.md`
- `Tag.tag_group_name` is a non-FK string join to `TagGroupDefinition.name` (viewonly relationship)
- `Article.metadata_` Python attribute maps to `metadata` DB column (underscore avoids SQLAlchemy reserved word)
- Translation uses a parallel-table pattern: `AnalysisTranslation`, `TagTranslation`, `TagGroupTranslation` each have a `language` column + unique constraint on `(parent_id, language)`. English content was normalized into translations by migration 17.
- `configure_mappers()` is called in `tag.py` to resolve circular mapper dependencies
- `ArxivKeyword` was legacy (superseded by `ScraperKeyword`) and has been deleted — its table no longer exists
- `MetricDefinition` (per `metric_key`, admin-editable `enabled`/`icon_name`) and `MetricProvider` (per `metric_key`+`provider_name`, maintainer-only extraction config) — see Metric Provider Chain above

### Observability

All optional with graceful no-op fallback: OpenTelemetry metrics/traces to Grafana Cloud, structlog + Loki for logging, Sentry for errors, MaxMind GeoIP2 for IP-to-country resolution. `RequestLoggingMiddleware` on backend logs every request. Frontend proxy route also logs requests to Loki.

### i18n

Custom `I18nProvider` context with locale files in `frontend/i18n/` (English + zh-TW). Auto-resolves language from IP via `/api/languages` endpoint. Translation is also done server-side via `TranslateArticleUseCase` and `TranslateTagsUseCase`.

### CI/CD

GitHub Actions on push/PR to `master`:
1. **migrate** — PR only; runs `alembic upgrade head` against the shared staging DB (skipped on push to master, since that would race `close-staging.yml` tearing the same staging deployments down post-merge — see `migrate` job comment in `ci.yml`)
2. **unit-test** → **integration-test** — Spins up postgres service container; integration tests need LLM API keys
3. **frontend-unit** → **frontend-e2e** — Vitest then Playwright (chromium)
4. **rollback** — PR only; if migrate succeeded but tests fail, auto-runs `alembic downgrade -1` on the staging DB
5. Coverage uploaded to Codecov; pass-rate badges updated via GitHub Gist

Production migration + deploy is a separate flow: `release.yml`, triggered by pushing a `v*` tag, runs `alembic upgrade head` against production DB (`scraper / production` environment) before deploying.

AI PR reviewer (`coderabbitai`) runs on all PRs.

## Key Conventions

- **Pydantic schemas** — some in `backend/schemas/`, many defined inline in routers
- **Alembic migrations** in `alembic/versions/` — numbered prefix (00–17); early ones use hex revision IDs, later ones use descriptive strings like `"05_normalize_tags"`
- **Dependency management** — `uv` with `uv.lock`, Python 3.11, dependency groups in `pyproject.toml`: core, scraper, backend, observability, dev
- **Frontend UI** — Shadcn/UI primitives in `components/ui/`, Tailwind CSS v4, Radix UI
- **Test markers** — `@pytest.mark.integration` for tests requiring postgres; integration test conftest creates `test_integration` schema with per-test rollback
- **Exception handling** — domain exceptions raised anywhere in `src/`/`backend/` must subclass `DomainError` (`shared/domain/exceptions.py`) via one of its shared categories (`ValidationError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `ExternalDependencyError`); a single central handler (`backend/exceptions/handlers.py`) maps these to HTTP status codes — routers never construct `HTTPException` themselves, with one documented exception: `chat.py`'s 429 rate-limit response, since 429 was never part of the `DomainError` category mapping (`specs/017-exception-handling-guideline/router-audit.md`). Full guideline: `site/guide/architecture/exception-handling.md`.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/020-redis-caching-layer/plan.md`.
<!-- SPECKIT END -->
