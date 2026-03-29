# Backend API

FastAPI service that exposes REST endpoints for the frontend. Handles article browsing, scraper configuration, user authentication, and knowledge graph queries. Shares the PostgreSQL database with the scraper service.

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
│   ├── graph.py                # GET /graph — tag relationship graph data
│   ├── scraper_settings.py     # CRUD for scraper source configuration
│   ├── auth.py                 # POST /login, /register, /refresh
│   └── arxiv_keywords.py       # CRUD for ArXiv keyword filters
└── schemas/
    ├── user.py
    ├── scraper_setting.py
    └── arxiv_keyword.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | DB connectivity check |
| `GET` | `/articles` | Paginated articles — supports `page`, `size`, `sort`, `order`, `sources[]`, `tags[]`, `q` |
| `GET` | `/graph` | Knowledge graph: tag nodes and article edges |
| `GET` | `/scraper_settings` | List active scraper sources |
| `POST` | `/scraper_settings` | Create a scraper source (RSS URL, blog selectors, or ArXiv keywords) |
| `PATCH` | `/scraper_settings/{id}` | Update a scraper source |
| `DELETE` | `/scraper_settings/{id}` | Remove a scraper source |
| `GET` | `/arxiv_keywords` | List ArXiv search keywords |
| `POST` | `/arxiv_keywords` | Add an ArXiv keyword |
| `DELETE` | `/arxiv_keywords/{id}` | Remove an ArXiv keyword |
| `POST` | `/login` | Email + password → JWT access + refresh token |
| `POST` | `/register` | Create user account |
| `POST` | `/refresh` | Exchange refresh token for new access token |
| `POST` | `/articles/{id}/tags` | Bulk assign tags to an article |

## Authentication

JWT bearer tokens issued on `/login`. Protected routes use the `guards.py` dependency which validates and decodes the token. Passwords are hashed with `bcrypt`. CORS is restricted to `FRONTEND_ORIGIN`.

## Deployment

| Context | File |
|---------|------|
| Production | `Dockerfile` (multi-stage; downloads MaxMind GeoLite2 DB) |
| Development | `Dockerfile.dev` |
| Config | `railway.toml` (Railway service definition) |

Environment variables required: `DATABASE_URL`, `JWT_SECRET`, `FRONTEND_ORIGIN`. Default port: `8000` (overridable via `PORT`).
