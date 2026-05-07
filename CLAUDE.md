# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend / Scraper (Python)

| Command | Purpose |
|---|---|
| `make test` | Run unit tests (`src/tests/unit/`) |
| `make test-integration` | Run integration tests (requires local postgres) |
| `make test-all-cov` | All tests with combined HTML coverage |
| `make scrape SOURCE=rss` | Manual scrape; supports `LIMIT=`, `DAYS_BACK=`, `NO_ANALYZE=1` |
| `make migrate` | Run `alembic upgrade head` locally |
| `make migrate-down` | Rollback one migration |
| `make dump` / `make sync` | Dump remote DB / restore to local postgres |
| `make retry-failed` | Retry failed tasks |
| `make translate LANG=zh-TW` | Translate article analyses |

Run a single test file: `uv run pytest src/tests/unit/test_foo.py`
Run a single test: `uv run pytest src/tests/unit/test_foo.py::test_bar -v`
Run backend tests: `uv run pytest backend/tests/`
Run script tests: `uv run pytest scripts/tests/`

### Frontend

| Command | Purpose |
|---|---|
| `cd frontend && npm run dev` | Next.js dev server (port 3000) |
| `cd frontend && npm run test` | Vitest unit tests |
| `cd frontend && npm run test:e2e` | Playwright E2E tests |
| `cd frontend && npm run lint` | ESLint |
| `cd frontend && npm run format` | Prettier |

### Docker

`docker compose up` — starts postgres (5432), backend (8000), frontend (3000), pgadmin (80), scraper app.

## Architecture

Three services sharing one PostgreSQL database:

- **`src/`** — Scraper/analyzer service (domain logic, scheduled scraping, LLM analysis, notifications)
- **`backend/`** — FastAPI REST API (port 8000) serving the frontend
- **`frontend/`** — Next.js 16 + React 19 web UI (port 3000)
- **`models/`** — Shared SQLAlchemy ORM models used by both `src/` and `backend/`

### API Proxy Pattern

The frontend does **not** call the backend directly. All API requests go through a Next.js catch-all reverse proxy at `frontend/app/api/proxy/[...path]/route.ts`, which forwards to `http://backend:8000`. Client code uses `apiFetch()` from `frontend/lib/api-fetch.ts` which prefixes paths with `/api/proxy`.

### Auth Flow

NextAuth v4 (JWT strategy) on frontend → `jose` signs HS256 JWT with `sub` (user ID) and `role` → JWT passed as `Authorization: Bearer` through proxy → `backend/auth/guards.py` validates with `NEXTAUTH_SECRET` and enforces `require_admin` / `require_user` via `Depends()`.

### Scraper Architecture (Hexagonal / DDD)

`src/` follows domain-driven design:

- **Domain layer** (`src/modules/*/domain/`) — Entities (`Article`, `Analysis`, `ScrapeJob`, `FailedTask`, `Topic`), value objects, repository interfaces, domain service interfaces (`Scraper`, `LLMService`)
- **Application layer** (`src/modules/*/application/`) — Use cases (`ProcessScrapedArticleUseCase`, `AnalyzeArticleUseCase`, `TranslateArticleUseCase`, `TranslateTagsUseCase`), event handlers, DTOs
- **Infrastructure layer** (`src/infrastructure/`) — Concrete implementations: scrapers (`RssScraper`, `BlogScraper`, `ArxivScraper` extending `BaseScraper`), LLM providers (`GeminiProvider`, `ClaudeProvider`, `OpenRouterProvider`), repositories, parsers, notifications, observability

### Scraper Pipeline Flow

1. **Discover** — Each scraper's `discover()` returns `List[ScrapeJob]` from RSS feeds, blog listings, or ArXiv API
2. **Pre-dedup** — Filter out URLs already analyzed (via `UrlHash`)
3. **Fetch** — `ScrapeExecutor` runs concurrent fetches (5 workers, per-host semaphore, robots.txt respect for blogs)
4. **Publish** — Scraped articles published as `ScrapedArticleDTO` on `InMemoryEventBus`
5. **Process** — `ArticleScrapedHandler` → `ProcessScrapedArticleUseCase` (dedup + save)
6. **Analyze** — `ArticleProcessedHandler` → `AnalyzeArticleUseCase` (LLM chain)
7. **Translate** — `AnalysisCompletedHandler` auto-triggers translation for configured languages
8. **Notify** — `PipelineCompletedEvent` triggers Telegram notifications and OTel metrics

### LLM Provider Chain

`ResilientLLMService` holds an ordered list of `ProviderHandler` objects (sorted by priority). Each pairs a provider with a `SlidingWindowStrategy` rate limiter (rpm/tpm/rpd). On `analyze()`, walks providers in priority order; falls back on `RateLimitExhausted` or any exception. Provider config lives in `providers.toml` at project root.

### Observability

All optional with graceful no-op fallback: OpenTelemetry metrics/traces to Grafana Cloud, structlog + Loki for logging, Sentry for errors, MaxMind GeoIP2 for IP-to-country resolution. `RequestLoggingMiddleware` on backend logs every request.

### i18n

Custom `I18nProvider` context with locale files in `frontend/i18n/` (English + zh-TW). Auto-resolves language from IP via `/api/languages` endpoint. Translation is also done server-side via `TranslateArticleUseCase` and `TranslateTagsUseCase`.

## Key Conventions

- **ORM models** in `models/` use UUID primary keys and share a single `Base = declarative_base()`
- **Pydantic schemas** — some in `backend/schemas/`, many defined inline in routers
- **Alembic migrations** in `alembic/versions/` — numbered prefix (00–16); CI auto-migrates on push to master and auto-rolls back if tests fail
- **Dependency management** — `uv` with `uv.lock`, Python 3.11, dependency groups in `pyproject.toml`: core, scraper, backend, observability, dev
- **Frontend UI** — Shadcn/UI primitives in `components/ui/`, Tailwind CSS v4, Zustand v5 for state, `TopicContext` with localStorage persistence
- **Test markers** — `@pytest.mark.integration` for tests requiring postgres; integration test conftest creates `test_integration` schema with per-test rollback
