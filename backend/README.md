[![backend unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=backend-unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=backend-unit)
[![backend integration coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=backend-integration)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=backend-integration)
![backend unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/backend-unit-passrate.json)
![backend integration tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/backend-integration-passrate.json)

# Backend API

FastAPI service that exposes REST endpoints for the frontend. Handles article browsing, tag group management, scraper configuration, user + guest authentication, knowledge graph queries, RAG chat proxying, and Grafana/monitoring data proxy. Shares the PostgreSQL database with the scraper service (`src/`).

## Architecture

```
backend/
├── main.py                     # FastAPI app init — registers routers, CORS, exception handlers,
│                                #   Sentry/OTel setup, /health
├── database.py                 # SQLAlchemy session dependency
├── config.py                   # Env var reads only — no DB imports, no side effects
├── constants.py                # SOURCE_CATEGORIES and other static lookups
├── observability.py            # Structured logging (+ optional Loki) and OTel tracing setup
├── auth/
│   └── guards.py                # JWT bearer guards: require_admin, require_user,
│                                 #   require_any_token, get_optional_user_id
├── exceptions/
│   └── handlers.py              # Central DomainError → HTTP status mapping (see below)
├── middleware/
│   └── logging.py               # Structured request/response logging (structlog)
├── routers/                     # 15 routers, one per resource — see table below
├── schemas/                     # Pydantic request/response models, one file per resource
└── services/                    # Business logic called by routers
```

## Authentication

JWT bearer tokens (HS256, `NEXTAUTH_SECRET`), issued by NextAuth on the frontend for real users, or by this backend itself for anonymous "guest" visitors. Guards live in `backend/auth/guards.py`:

| Guard | Accepts | Rejects with |
|---|---|---|
| `require_admin` | Valid, non-expired JWT with `role == "admin"` | 401 (missing/invalid/expired) or 403 (wrong role) |
| `require_user` | Valid, non-expired JWT for a real user/admin (`role` claim present) | 401 — explicitly rejects guest tokens too |
| `require_any_token` | A real user/admin token **or** a guest *access* token (`tier: "guest"`, `token_use: "access"`) | 401 — a guest *refresh* token is never accepted here |
| `get_optional_user_id` | Any of the above, or nothing | Never raises — returns `None` on missing/invalid/expired |

`require_any_token` is the floor requirement for nearly every data-reading endpoint below — anonymous visitors are never actually unauthenticated on the wire; the frontend transparently bootstraps a guest token first (see `POST /auth/guest`).

### Guest tokens

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/guest` | No credentials required. Returns a fresh `{access_token, refresh_token, expires_in}` pair (`sub`-less, `tier: "guest"`, access token TTL 1h, refresh token TTL 30d) |
| `POST` | `/auth/guest/refresh` | Exchange a valid, non-expired guest refresh token for a new access token with the same `guest_id` |

Passwords are hashed with `bcrypt`. CORS is restricted to `FRONTEND_ORIGIN`. Google OAuth uses `python-jose` to decode tokens forwarded from NextAuth.

## Error Handling

Every domain exception raised anywhere in `src/`/`backend/` subclasses `DomainError` (`shared/domain/exceptions.py`) via one of 6 shared categories. `backend/exceptions/handlers.py` registers a single central handler that maps them to HTTP status + a uniform `{"error": {"code", "message", "request_id"}}` body — routers never construct `HTTPException` directly (the one documented exception is `chat.py`'s `429` rate-limit response, since 429 was never in the category mapping):

| Category | Status |
|---|---|
| `ValidationError` | 400 |
| `UnauthorizedError` | 401 |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `ExternalDependencyError` | 502 |
| (unmapped `DomainError`, or a bare `Exception` safety net) | 500 |

500/502 responses are sanitized (never leak `str(exception)`, a stack trace, or raw SQL) and reported to Sentry; 4xx are not, since they're expected/recoverable, not bugs. Full guideline: `site/guide/architecture/exception-handling.md`.

## Routers

| Router | Prefix | Auth |
|---|---|---|
| `articles.py` | — | `require_any_token`; `POST /admin/articles/flush-view-counts` is `require_admin` |
| `auth.py` | `/auth` | Mixed — see [Authentication](#authentication) and table below |
| `chat.py` | — | `require_any_token` |
| `grafana.py` | `/grafana` | All `require_admin` |
| `graph.py` | — | `require_any_token` |
| `languages.py` | — | `require_any_token` |
| `llm_providers.py` | `/llm-providers` | All `require_admin` |
| `metric_definitions.py` | — | `GET /metric-definitions` public; `/admin/metric-definitions` `require_admin` |
| `monitoring.py` | — | **No auth dependency** — a gap, not a designed public tier (every sibling data router was migrated to `require_any_token`; this one appears to have been missed) |
| `scraper_keywords.py` | `/scraper-keywords` | All `require_admin` |
| `scraper_settings.py` | `/scraper-settings` | All `require_admin` |
| `tags.py` | — | Read (`GET /tag-groups*`) `require_any_token`; writes `require_admin` |
| `topics.py` | `/topics` | `GET /topics` `require_any_token`; writes `require_admin` |
| `user.py` | `/user` | All `require_user` (guest tokens rejected — these are account-scoped) |
| `weekly_reports.py` | `/weekly-reports` | All `require_any_token` |

## API Endpoints

### Articles

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/articles` | Paginated list — filters by source/aggregator/original_source/tag/tag_group/date range/topic_id/favorites_only; `sort` accepts any metric_key |
| `GET` | `/source-categories` | Static list of source categories |
| `GET` | `/articles/filters/sources` | Distinct source values for filter UI |
| `GET` | `/articles/filters/original-sources` | Distinct original_source values |
| `GET` | `/articles/filters/tags` | Distinct tag values |
| `GET` | `/articles/{article_id}` | Full article detail — translations, tag groups, metrics, view count |
| `POST` | `/articles/{article_id}/view` | Increment view count (Redis, 24h per-IP dedup) |
| `POST` | `/admin/articles/flush-view-counts` | admin — flush buffered Redis view counts into `article_metrics` |

### Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/verify` | — | Username + password → user info (backs the NextAuth credentials provider) |
| `POST` | `/auth/register` | — | Register via credentials or Google (`google_id` in body) |
| `POST` | `/auth/google/authorize` | — | Look up an existing user by email for Google sign-in |
| `GET` | `/auth/users` | admin | List all users |
| `POST` | `/auth/users` | admin | Create user |
| `PATCH` | `/auth/users/{id}` | admin | Update user |
| `DELETE` | `/auth/users/{id}` | admin | Delete user |
| `GET` | `/auth/me` | user | Own profile |
| `PATCH` | `/auth/me` | user | Update own profile |
| `POST` | `/auth/me/password` | user | Change password |
| `DELETE` | `/auth/me` | user | Delete own account |
| `POST` | `/auth/me/link-google` | user | Link Google account |
| `DELETE` | `/auth/me/link-google` | user | Unlink Google account |
| `POST` | `/auth/guest` | — | Issue a guest access + refresh token pair |
| `POST` | `/auth/guest/refresh` | — | Exchange a guest refresh token for a new access token |

### Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/completions` | SSE-streaming proxy to `chatbot-plugin`'s OpenAI-compatible `/v1/chat/completions`; enforces a per-tier daily quota via Redis (guest: 3/day, user: 10/day) — returns `429` on quota exhaustion; mid-stream upstream failures are signaled in-band as an `{"error": {...}}` SSE frame, not an HTTP status, since the response is already committed once streaming starts |
| `GET` | `/chat/quota` | Remaining/limit for the caller's tier |

### Topics (`/topics`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/topics` | any token | List active topics (`?include_inactive=` for admin views) |
| `POST` | `/topics` | admin | Create topic |
| `PATCH` | `/topics/{id}` | admin | Update topic |
| `DELETE` | `/topics/{id}` | admin | Soft-delete topic |

### Tag Groups & Tags

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/tag-groups` | any token | List tag groups (`?topic_id=`, `?include_similarity=`) incl. a synthetic "ungrouped" bucket |
| `POST` | `/tag-groups` | admin | Create tag group (triggers Gemini embedding) |
| `POST` | `/tag-groups/merge` | admin | Merge two tag groups into one |
| `POST` | `/tag-groups/reorder` | admin | Bulk update sort_order |
| `GET` | `/tag-groups/{id}` | any token | Single tag group with tags |
| `PUT` | `/tag-groups/{id}` | admin | Rename / recolor tag group |
| `DELETE` | `/tag-groups/{id}` | admin | Delete tag group |
| `PUT` | `/tags/{id}` | admin | Rename tag / move to group / ungroup |
| `DELETE` | `/tags/{id}` | admin | Delete tag |
| `POST` | `/tags/batch-move` | admin | Move multiple tags to a different group |
| `GET` | `/tag-normalization-suggestions` | admin | List pending suggestions |
| `POST` | `/tag-normalization-suggestions/{id}/approve` | admin | Approve — merges tags |
| `POST` | `/tag-normalization-suggestions/{id}/reject` | admin | Reject suggestion |

### Scraper Settings (`/scraper-settings`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/scraper-settings` | admin | List sources (`?topic_id=`) |
| `POST` | `/scraper-settings` | admin | Create source (RSS, blog selectors, ArXiv/OpenAlex/Semantic Scholar keywords) |
| `PATCH` | `/scraper-settings/{id}` | admin | Update source |
| `DELETE` | `/scraper-settings/{id}` | admin | Remove source |

### Scraper Keywords (`/scraper-keywords`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/scraper-keywords` | admin | List keywords (`?topic_id=`, `?keyword_type=`) |
| `POST` | `/scraper-keywords` | admin | Add keyword |
| `DELETE` | `/scraper-keywords/{id}` | admin | Remove keyword |

### LLM Providers (`/llm-providers`)

DB-driven — no config file. See CLAUDE.md's "LLM Provider Chain" section.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/llm-providers` | admin | List providers |
| `POST` | `/llm-providers` | admin | Create provider |
| `PUT` | `/llm-providers/reorder` | admin | Bulk update priority order |
| `PATCH` | `/llm-providers/{id}` | admin | Update provider |
| `DELETE` | `/llm-providers/{id}` | admin | Delete provider |

### Metric Definitions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/metric-definitions` | — (public) | Display metadata for enabled catalog metrics only |
| `GET` | `/admin/metric-definitions` | admin | All metric definitions, admin view |
| `PATCH` | `/admin/metric-definitions/{id}` | admin | Toggle `enabled` / `icon_name` |

### Weekly Reports (`/weekly-reports`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/weekly-reports` | Paginated list (`?topic_id=`, `?limit=`, `?offset=`, `?lang=`) |
| `GET` | `/weekly-reports/latest` | Most recent report for a topic |
| `GET` | `/weekly-reports/weeks` | Week-start dates with a completed report |
| `GET` | `/weekly-reports/by-week` | Report for a specific week (normalized to Monday) |

### User (`/user`)

Account-scoped — `require_user` only, no guest access.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/user/favorites` | List favorited article IDs |
| `POST` | `/user/favorites/{article_id}` | Add favorite |
| `DELETE` | `/user/favorites/{article_id}` | Remove favorite |
| `GET` | `/user/subscriptions` | List subscribed topic IDs |
| `POST` | `/user/subscriptions` | Subscribe to topic |
| `DELETE` | `/user/subscriptions/{topic_id}` | Unsubscribe |
| `GET` | `/user/notification-settings` | Get notification prefs (email/telegram/locale) |
| `PUT` | `/user/notification-settings` | Upsert notification prefs |

### Grafana Proxy (`/grafana`)

All `require_admin`. Each returns `503 {"error": "not_configured"}` if the relevant `GRAFANA_*` env vars are unset.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/grafana/metrics` | Query Prometheus metrics |
| `POST` | `/grafana/metrics/batch` | Batch metric queries |
| `GET` | `/grafana/logs` | Query Loki logs |
| `POST` | `/grafana/loki-metrics/batch` | Batch Loki-as-metrics queries |
| `POST` | `/grafana/logs/batch` | Batch log queries |
| `GET` | `/grafana/traces` | Query Tempo traces |
| `GET` | `/grafana/traces/{trace_id}` | Single trace detail |
| `POST` | `/grafana/traces/batch` | Batch trace queries |

### Other

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | — | DB connectivity check (`{"status": "ok", "db": "ok"}`, 503 on failure) |
| `GET` | `/languages` | any token | Resolve client language from IP via GeoIP2 |
| `GET` | `/failed-tasks` | — (no guard) | Paginated failed pipeline tasks |

## Observability

`backend/observability.py`, gated on env vars with a no-op fallback for local dev:

- **Logging** — stdout + structlog JSON always; an optional Loki handler (`python-logging-loki`) when `GRAFANA_LOKI_URL`/`GRAFANA_LOKI_USER`/`GRAFANA_API_KEY` are all set. A structlog processor injects the current OTel `trace_id`/`span_id` into every log line.
- **Tracing** — an OTel `TracerProvider` exporting to Grafana Cloud OTLP/HTTP when `GRAFANA_OTLP_ENDPOINT`/`GRAFANA_OTLP_USER`/`GRAFANA_API_KEY` are set; `FastAPIInstrumentor` auto-instruments every request except `/health`.
- **Errors** — `sentry_sdk.init(dsn=SENTRY_DSN)` in `main.py`; the central exception handler reports every 500/502.

## Deployment

| Context | File |
|---------|------|
| Production | `Dockerfile` (multi-stage; downloads MaxMind GeoLite2 DB) |
| Development | `Dockerfile.dev` |
| Config | `railway.toml` (Railway service definition) |

Deployed via this monorepo's CI (`railway up` — staging on PR, production on version tag; see the root `.specify/memory/constitution.md` Principle V), not Railway's own branch-watch auto-deploy.

Environment variables read by `backend/config.py` (19 total): `DATABASE_URL`, `FRONTEND_ORIGIN`, `VIEW_COUNT_FLUSH_INTERVAL`, `SWAGGER_TRY_IT_OUT_ENABLED`, `NEXTAUTH_SECRET`, `APP_ENV`, `REDIS_URL`, `CHAT_SERVICE_URL`, `CHAT_SERVICE_API_KEY`, `GEMINI_API_KEY`, `SENTRY_DSN`, `GRAFANA_PROMETHEUS_URL`, `GRAFANA_PROMETHEUS_USER`, `GRAFANA_API_KEY`, `GRAFANA_LOKI_URL`, `GRAFANA_LOKI_USER`, `GRAFANA_TEMPO_URL`, `GRAFANA_TEMPO_USER`, `GRAFANA_OTLP_ENDPOINT`, `GRAFANA_OTLP_USER`. Required at minimum: `DATABASE_URL`, `NEXTAUTH_SECRET`, `FRONTEND_ORIGIN`. Default port: `8000` (overridable via `PORT`).
