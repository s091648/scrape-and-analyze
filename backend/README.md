[![backend unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=backend-unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=backend-unit)
[![backend integration coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=backend-integration)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=backend-integration)
![backend unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/backend-unit-passrate.json)
![backend integration tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/backend-integration-passrate.json)

# Backend API

FastAPI service that exposes REST endpoints for the frontend. Handles article browsing, tag group management, scraper configuration, user authentication, knowledge graph queries, and Grafana/monitoring data proxy. Shares the PostgreSQL database with the scraper service.

## Architecture

```
backend/
├── main.py                     # FastAPI app init — registers routers, CORS, middleware
├── database.py                 # SQLAlchemy session dependency
├── middleware/
│   └── logging.py              # Structured request/response logging (structlog)
├── auth/
│   └── guards.py               # JWT bearer token validation (python-jose)
├── routers/
│   ├── articles.py             # GET /articles — paginated search with filtering
│   ├── graph.py                # GET /analyses/graph — tag relationship graph data
│   ├── auth.py                 # /auth — login, register, user management
│   ├── topics.py               # /topics — topic CRUD
│   ├── tags.py                 # /tag-groups, /tags — tag group + tag management
│   ├── scraper_settings.py     # /scraper-settings — scraper source CRUD
│   ├── scraper_keywords.py     # /scraper-keywords — keyword filter CRUD
│   ├── llm_providers.py        # /llm-providers — LLM provider CRUD
│   ├── grafana.py              # /grafana — metrics/logs/traces proxy for Grafana
│   ├── monitoring.py           # /failed-tasks — failed pipeline task listing
│   └── languages.py            # /languages — IP→language resolution (GeoIP)
└── schemas/
    ├── user.py
    ├── topic.py
    ├── tag.py
    ├── scraper_setting.py
    └── scraper_keyword.py
```

## Routers

| Router | Prefix | Auth | Endpoints |
|--------|--------|------|-----------|
| `articles.py` | `/` | Public | 6 |
| `graph.py` | `/` | Public | 2 |
| `auth.py` | `/auth` | Mixed (admin / require_user / public) | 13 |
| `topics.py` | `/topics` | Write ops require_admin | 4 |
| `tags.py` | `/` | Write ops require_admin | 13 |
| `scraper_settings.py` | `/scraper-settings` | All require_admin | 4 |
| `scraper_keywords.py` | `/scraper-keywords` | All require_admin | 3 |
| `llm_providers.py` | `/llm-providers` | All require_admin | 5 |
| `grafana.py` | `/grafana` | All require_admin | 8 |
| `monitoring.py` | `/` | Public | 1 |
| `languages.py` | `/` | Public | 1 |

## API Endpoints

### Articles

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/articles` | Paginated list — `page`, `size`, `sort`, `order`, `sources[]`, `original_sources[]`, `tag_groups[]`, `topic_id`, `published_after/before`, `scraped_after/before` |
| `GET` | `/source-categories` | List distinct source categories |
| `GET` | `/articles/filters/sources` | Distinct source values for filter UI |
| `GET` | `/articles/filters/original-sources` | Distinct original_source values |
| `GET` | `/articles/filters/tags` | Distinct tag group names |
| `GET` | `/articles/{article_id}` | Article detail with tag groups |
| `GET` | `/failed-tasks` | Paginated failed pipeline tasks |

### Graph

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analyses/graph` | Knowledge graph nodes + edges (`?aggregator=`, `?topic_id=`, `?days=`) |
| `GET` | `/analyses/graph/group/{name}` | Articles for a specific tag group |

### Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/verify` | — | Email + password → JWT access + refresh token |
| `POST` | `/auth/register` | — | Create user account |
| `POST` | `/auth/google/authorize` | — | Google OAuth sign-in / sign-up |
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

### Topics (`/topics`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/topics` | — | List active topics |
| `POST` | `/topics` | admin | Create topic |
| `PATCH` | `/topics/{id}` | admin | Update topic |
| `DELETE` | `/topics/{id}` | admin | Soft-delete topic |

### Tag Groups & Tags

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/tag-groups` | — | List tag groups (`?topic_id=`, `?include_similarity=`) |
| `POST` | `/tag-groups` | admin | Create tag group (triggers Gemini embedding) |
| `POST` | `/tag-groups/merge` | admin | Merge two tag groups into one |
| `POST` | `/tag-groups/reorder` | admin | Bulk update sort_order |
| `GET` | `/tag-groups/{id}` | — | Single tag group with tags |
| `PUT` | `/tag-groups/{id}` | admin | Rename / recolor tag group |
| `DELETE` | `/tag-groups/{id}` | admin | Delete tag group |
| `PUT` | `/tags/{id}` | admin | Rename tag |
| `DELETE` | `/tags/{id}` | admin | Delete tag |
| `POST` | `/tags/batch-move` | admin | Move multiple tags to a different group |
| `GET` | `/tag-normalization-suggestions` | admin | List normalization suggestions |
| `POST` | `/tag-normalization-suggestions/{id}/approve` | admin | Approve suggestion |
| `POST` | `/tag-normalization-suggestions/{id}/reject` | admin | Reject suggestion |

### Scraper Settings (`/scraper-settings`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/scraper-settings` | admin | List sources (with 14-day activity histogram) |
| `POST` | `/scraper-settings` | admin | Create source (RSS, blog selectors, ArXiv keywords) |
| `PATCH` | `/scraper-settings/{id}` | admin | Update source |
| `DELETE` | `/scraper-settings/{id}` | admin | Remove source |

### Scraper Keywords (`/scraper-keywords`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/scraper-keywords` | admin | List keywords |
| `POST` | `/scraper-keywords` | admin | Add keyword |
| `DELETE` | `/scraper-keywords/{id}` | admin | Remove keyword |

### LLM Providers (`/llm-providers`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/llm-providers` | admin | List providers |
| `POST` | `/llm-providers` | admin | Create provider |
| `PUT` | `/llm-providers/reorder` | admin | Bulk update priority order |
| `PATCH` | `/llm-providers/{id}` | admin | Update provider |
| `DELETE` | `/llm-providers/{id}` | admin | Delete provider |

### Grafana Proxy (`/grafana`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/grafana/metrics` | admin | Query Prometheus/Grafana metrics |
| `POST` | `/grafana/metrics/batch` | admin | Batch metric queries |
| `GET` | `/grafana/logs` | admin | Query Loki logs |
| `POST` | `/grafana/loki-metrics/batch` | admin | Batch Loki metric queries |
| `POST` | `/grafana/logs/batch` | admin | Batch log queries |
| `GET` | `/grafana/traces` | admin | Query Tempo traces |
| `GET` | `/grafana/traces/{trace_id}` | admin | Single trace detail |
| `POST` | `/grafana/traces/batch` | admin | Batch trace queries |

### Other

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | DB connectivity check (`{"status": "ok", "db": "ok"}`) |
| `GET` | `/languages` | Resolve client language from IP via GeoIP2 |

## Authentication

JWT bearer tokens issued on `POST /auth/verify`. Protected routes use `guards.py` dependencies:

- `require_admin` — validates JWT and enforces `role == "admin"`
- `require_user` — validates JWT only (any authenticated user)

Passwords are hashed with `bcrypt`. CORS is restricted to `FRONTEND_ORIGIN`. Google OAuth uses `jose` to decode tokens from NextAuth.

## Deployment

| Context | File |
|---------|------|
| Production | `Dockerfile` (multi-stage; downloads MaxMind GeoLite2 DB) |
| Development | `Dockerfile.dev` |
| Config | `railway.toml` (Railway service definition) |

Environment variables required: `DATABASE_URL`, `NEXTAUTH_SECRET`, `FRONTEND_ORIGIN`. Optional: `GEMINI_API_KEY` (tag embedding), `MAXMIND_LICENSE_KEY` (GeoIP), `GRAFANA_*` (Grafana proxy). Default port: `8000` (overridable via `PORT`).
