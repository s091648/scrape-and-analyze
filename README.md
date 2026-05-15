[![codecov](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64)](https://codecov.io/gh/s091648/scrape-and-analyze)

# Scrape & Analyze

A web scraping and AI-powered article analysis platform. Articles are automatically discovered from RSS feeds, blogs, and ArXiv, analyzed by LLMs to extract insights and tags, then served through a web UI for browsing and exploration.

## Concept
[![Notion](https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=notion&logoColor=white)](https://www.notion.so/sweetfatotaku/Chapter-9-Deisgn-a-Web-Crawler-3176d4fc5ccf8114aa4cceb952db9fca?source=copy_link)
![Common Web Crawler](images/diagrams/common_web_crawler.png)
The overall design is greatly inspired by the Chapter 9 of System Design Interview by Alex Xu.

As we're not trying to crawl every content possible across the whole world-wide web but just request contents from particular sources, the complexity of analyzing the structure and building a tree for the web pages are avoided.

However, useful concepts such as politeness are taken into consideration.

## Architecture

```
┌──────────────────────────────────────────────┐
│            Frontend  (Next.js 16)            │
│  Article browse · Knowledge graph · Admin    │
│  NextAuth v4 · Tailwind · Shadcn/UI          │
│  Port 3000                                   │
└────────────────────┬─────────────────────────┘
                     │ HTTP /api/proxy/**
┌────────────────────▼─────────────────────────┐
│            Backend API  (FastAPI)            │
│  /articles · /graph · /scraper_settings      │
│  JWT auth · CORS · structlog                 │
│  Port 8000                                   │
└────────────────────┬─────────────────────────┘
                     │ SQLAlchemy ORM
┌────────────────────▼─────────────────────────┐
│               PostgreSQL                     │
│  articles · analysis · tags                  │
│  scraper_settings · users · arxiv_keywords   │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│       Scraper / Analyzer  (src/)             │
│  Scheduled job — reads scraper_settings,     │
│  fetches RSS / blog / ArXiv articles,        │
│  analyzes with LLM chain (Gemini → OpenRouter│
│  fallback), writes results to shared DB      │
└────────────────────┬─────────────────────────┘
                     │ SQLAlchemy ORM (same DB)
                     ▼
              (same PostgreSQL)
```

## Services

| Directory | Role | Tech |
|-----------|------|------|
| [`frontend/`](./frontend/) | Web UI | Next.js 16, React 19, TypeScript, Tailwind CSS |
| [`backend/`](./backend/) | REST API | FastAPI, Python 3.11, python-jose (JWT) |
| [`src/`](./src/) | Scraper & analyzer | Python 3.11, SQLAlchemy, BeautifulSoup, PyMuPDF |

## Data Flow

1. **Configure** — Admin adds scraper sources (RSS URL, blog CSS selectors, ArXiv keywords) via the web UI
2. **Scrape** — The `src/` service runs on a schedule, dispatches 3 parallel workers per source type, deduplicates by URL hash
3. **Analyze** — Each article is sent to the LLM provider chain; Gemini is tried first, OpenRouter is the fallback; rate limiting is enforced per provider
4. **Store** — Results (tags, pain points, insights) land in PostgreSQL
5. **Browse** — Frontend fetches paginated articles from the FastAPI backend; users can filter by source, tag, and date, or explore tag relationships in the knowledge graph

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS v4, Shadcn/UI, Zustand |
| Backend API | FastAPI 0.111, Uvicorn, python-jose, bcrypt |
| Scraper | Python 3.11, BeautifulSoup4, feedparser, PyMuPDF, httpx |
| LLM | Google Gemini, OpenRouter (configurable via `providers.toml`) |
| Database | PostgreSQL 15, SQLAlchemy 2.0, Alembic |
| Auth | NextAuth v4 (JWT + cookies), optional Google OAuth2 |
| Observability | structlog, Sentry, Grafana Loki, OpenTelemetry |
| Deployment | Docker Compose (local), Railway (production) |
| Testing | pytest (unit + integration), Vitest, Playwright |

## Local Development

```bash
# Start all services (postgres, backend, frontend, scraper)
docker compose up

# Run database migrations
make migrate

# Backend tests
docker compose run --rm job_service pytest tests/

# Frontend tests
cd frontend && npm run test         # unit (Vitest)
cd frontend && npm run test:e2e     # E2E (Playwright)
```