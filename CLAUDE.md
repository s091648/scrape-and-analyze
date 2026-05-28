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

### Backend Routers

| Router | Prefix | Auth |
|---|---|---|
| `articles.py` | `/` | Public |
| `auth.py` | `/auth` | Admin on user mgmt; `require_user` on `/me` |
| `graph.py` | `/` | Public |
| `scraper_settings.py` | `/scraper-settings` | All require_admin |
| `topics.py` | `/topics` | Write ops require_admin |
| `scraper_keywords.py` | `/scraper-keywords` | All require_admin |
| `languages.py` | `/api` | Public (resolves language from client IP via GeoIP) |

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

`ResilientLLMService` holds an ordered list of `ProviderHandler` objects (sorted by priority). Each pairs a provider with a `SlidingWindowStrategy` rate limiter (rpm/tpm/rpd). On `analyze()`, walks providers in priority order; falls back on `RateLimitExhausted` or any exception. Provider config lives in `providers.toml` at project root:

```toml
[[providers]]
name = "gemini"           # "gemini", "claude", or "openrouter"
priority = 1              # lower = tried first
model = "gemini-3-flash-preview"
api_key_env = "GEMINI_API_KEY"

[providers.strategy]
type = "sliding_window"
rpm = 5
tpm = 1000000
rpd = 20
```

### ORM Models

All models in `models/` use UUID primary keys and share a single `Base = declarative_base()`.

- `User` lives in the `auth` PostgreSQL schema (`__table_args__ = {'schema': 'auth'}`)
- `Tag.tag_group_name` is a non-FK string join to `TagGroupDefinition.name` (viewonly relationship)
- `Article.metadata_` Python attribute maps to `metadata` DB column (underscore avoids SQLAlchemy reserved word)
- Translation uses a parallel-table pattern: `AnalysisTranslation`, `TagTranslation`, `TagGroupTranslation` each have a `language` column + unique constraint on `(parent_id, language)`. English content was normalized into translations by migration 17.
- `configure_mappers()` is called in `tag.py` to resolve circular mapper dependencies
- `ArxivKeyword` is legacy — superseded by `ScraperKeyword`

### Observability

All optional with graceful no-op fallback: OpenTelemetry metrics/traces to Grafana Cloud, structlog + Loki for logging, Sentry for errors, MaxMind GeoIP2 for IP-to-country resolution. `RequestLoggingMiddleware` on backend logs every request. Frontend proxy route also logs requests to Loki.

### i18n

Custom `I18nProvider` context with locale files in `frontend/i18n/` (English + zh-TW). Auto-resolves language from IP via `/api/languages` endpoint. Translation is also done server-side via `TranslateArticleUseCase` and `TranslateTagsUseCase`.

### CI/CD

GitHub Actions on push/PR to `master`:
1. **migrate** — Auto-runs `alembic upgrade head` on production DB on push to master
2. **unit-test** → **integration-test** — Spins up postgres service container; integration tests need LLM API keys
3. **frontend-unit** → **frontend-e2e** — Vitest then Playwright (chromium)
4. **rollback** — If migrate succeeded but tests fail, auto-runs `alembic downgrade -1` on production DB
5. Coverage uploaded to Codecov; pass-rate badges updated via GitHub Gist

AI PR reviewer (`coderabbitai`) runs on all PRs.

## Key Conventions

- **Pydantic schemas** — some in `backend/schemas/`, many defined inline in routers
- **Alembic migrations** in `alembic/versions/` — numbered prefix (00–17); early ones use hex revision IDs, later ones use descriptive strings like `"05_normalize_tags"`
- **Dependency management** — `uv` with `uv.lock`, Python 3.11, dependency groups in `pyproject.toml`: core, scraper, backend, observability, dev
- **Frontend UI** — Shadcn/UI primitives in `components/ui/`, Tailwind CSS v4, Radix UI
- **Test markers** — `@pytest.mark.integration` for tests requiring postgres; integration test conftest creates `test_integration` schema with per-test rollback

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/001-article-collection/plan.md`.
<!-- SPECKIT END -->
