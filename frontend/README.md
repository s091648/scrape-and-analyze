[![frontend unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=frontend-unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=frontend-unit)
![frontend unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-unit-passrate.json)
![frontend e2e tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-e2e-passrate.json)

[![Notion](https://img.shields.io/badge/Storybook-FF4785?logo=storybook&logoColor=white)](https://satisfied-luck-production.up.railway.app/)

# Frontend

Next.js 16 + React 19 web application for browsing AI-analyzed articles, managing scraper sources, visualizing tag relationships as a knowledge graph, and administering LLM providers.

## Architecture

```
frontend/
├── app/                              # Next.js App Router
│   ├── page.tsx                      # Home — article browse entry point
│   ├── layout.tsx                    # Root layout (SessionProvider, TopicProvider, I18nProvider, NavBar)
│   ├── layout-shell.tsx              # Inner shell with ErrorBoundary
│   ├── home-page-content.tsx         # Article grid with pagination and filters
│   ├── articles/
│   │   └── [articleId]/page.tsx      # Full article detail page
│   ├── tags/page.tsx                 # Tag browser + normalization suggestions
│   ├── graph/page.tsx                # Knowledge graph visualization
│   ├── login/ & register/            # Auth pages
│   ├── settings/                     # Scraper source configuration UI
│   ├── admin/
│   │   ├── llm-providers/page.tsx    # LLM provider CRUD (priority, rpm/tpm/rpd, is_active)
│   │   ├── monitoring/               # Observability dashboard (traces, logs, metrics, Grafana)
│   │   ├── scraper-settings/         # RSS / blog / ArXiv / OpenAlex / Semantic Scholar sources
│   │   ├── topics/                   # Topic management
│   │   └── user-management/          # User admin
│   └── api/
│       ├── auth/[[...nextauth]]/     # NextAuth route handlers
│       ├── proxy/[...path]/          # Catch-all reverse proxy → backend:8000
│       ├── grafana-embed/            # Grafana panel embed proxy (signed URLs)
│       └── link-google/              # Google OAuth2 account linking (start + callback)
├── components/
│   ├── common/
│   │   ├── date-filter.tsx           # Reusable date-range picker
│   │   ├── error-boundary.tsx        # React error boundary
│   │   └── multi-select-popover.tsx  # Shared multi-select dropdown primitive
│   ├── features/
│   │   ├── articles/
│   │   │   ├── article-card.tsx          # Article display card (title, preview, source, tags)
│   │   │   ├── article-card-skeleton.tsx # Loading skeleton
│   │   │   ├── article-detail-dialog.tsx # Full article detail dialog
│   │   │   ├── filter-bar.tsx            # Multi-select filters: sources, aggregators, original_sources, tags, date
│   │   │   ├── grouped-tag-select.tsx    # Tag selector grouped by tag group
│   │   │   └── source-utils.ts           # Source display helpers
│   │   ├── graph/
│   │   │   └── knowledge-graph.tsx       # Force-directed graph (?aggregator=&original_source=&tag=)
│   │   ├── monitoring/
│   │   │   ├── article-workflow-dialog.tsx  # Per-article pipeline trace viewer
│   │   │   ├── failed-task-list.tsx         # Failed tasks table with retry
│   │   │   ├── grafana-panel.tsx            # Embedded Grafana panel
│   │   │   ├── log-detail-dialog.tsx        # Structured log detail
│   │   │   ├── logs-table.tsx               # Loki log stream table
│   │   │   ├── metrics-chart.tsx            # OTel metrics chart
│   │   │   ├── run-waterfall-dialog.tsx     # Pipeline run waterfall trace
│   │   │   ├── stage-card.tsx               # Pipeline stage summary card
│   │   │   ├── stat-card.tsx                # Metric stat card
│   │   │   └── traces-table.tsx             # OTel traces table
│   │   ├── navigation/
│   │   │   ├── nav-bar.tsx                  # Header with auth state
│   │   │   └── release-notes-popover.tsx    # Changelog popover
│   │   ├── scraper/
│   │   │   ├── arxiv-keyword-manager.tsx             # ArXiv search term manager
│   │   │   ├── openalex-keyword-manager.tsx          # OpenAlex keyword manager
│   │   │   ├── semantic-scholar-keyword-manager.tsx  # Semantic Scholar keyword manager
│   │   │   ├── scraper-source-card.tsx               # Display + inline-edit a scraper config
│   │   │   └── scraper-source-form.tsx               # Add RSS / blog / ArXiv / OpenAlex / SemanticScholar sources
│   │   └── tags/
│   │       ├── merge-group-dialog.tsx    # Merge tag groups dialog
│   │       ├── pending-changes-panel.tsx # Review + commit pending tag changes
│   │       ├── pending-suggestions.tsx   # Tag normalization suggestion list
│   │       ├── tag-dialog.tsx            # Tag create/edit dialog
│   │       ├── tag-group-card.tsx        # Tag group with its tags
│   │       └── tag-mode-selector.tsx     # Toggle between browse / normalization modes
│   ├── providers/
│   │   └── session-provider.tsx          # NextAuth SessionProvider wrapper
│   └── ui/                               # Shadcn/UI primitives (button, card, dialog, table, etc.)
├── hooks/
│   └── use-pagination.ts               # Shared pagination + filter state hook
├── lib/
│   ├── api/                            # Typed API client modules (one per backend router)
│   │   ├── articles.ts                 # Articles API (filters: aggregator, original_source, tag)
│   │   ├── auth.ts
│   │   ├── client.ts                   # apiFetch() — attaches JWT, prefixes /api/proxy, appends lang
│   │   ├── grafana.ts                  # Grafana Cloud API (traces, logs, metrics)
│   │   ├── graph.ts                    # Graph API (?aggregator=&original_source=&tag=)
│   │   ├── llm-providers.ts            # LLM providers CRUD
│   │   ├── scraper-keywords.ts
│   │   ├── scraper-settings.ts
│   │   ├── source-categories.ts
│   │   ├── tags.ts                     # Tags + normalization suggestions
│   │   └── topics.ts
│   ├── providers/
│   │   ├── guest-mode-provider.tsx     # Guest paywall state (6-article limit)
│   │   ├── i18n-provider.tsx           # Custom i18n (en + zh-TW, auto-resolves from IP)
│   │   ├── index.tsx                   # Composes all providers
│   │   └── topic-provider.tsx          # Active topic context (localStorage persistence)
│   ├── auth.ts                         # NextAuth config (JWT, Google providers)
│   ├── loki-logger.ts                  # Client-side Loki log shipping
│   ├── observability-constants.ts      # Shared OTel attribute names
│   ├── otlp-utils.ts                   # OTel trace/metric helpers
│   └── utils.ts                        # General utilities (cn, etc.)
├── middleware.ts                       # NextAuth route protection
├── globals.css                         # Tailwind CSS v4 theme + global styles
├── tests/
│   ├── unit/                           # Vitest + React Testing Library (40+ test files)
│   └── integration/                    # Playwright E2E (articles, article-detail, graph, monitoring, etc.)
│       └── fixtures/                   # Auth state, API handlers, token generator
├── __tests__/api/                      # Next.js API route unit tests (proxy redaction, grafana-embed)
├── vitest.config.ts
└── playwright.config.ts
```

## Key Features

| Feature | Details |
|---------|---------|
| **Article Browse** | Paginated grid (6 cards/page for guests, unlimited for users) |
| **Article Detail** | Full detail page at `/articles/[articleId]` |
| **Filtering** | Multi-select: sources, aggregators, original_sources, tags, date range |
| **Full-text Search** | `q` query param forwarded to `/articles` API |
| **Knowledge Graph** | `react-force-graph-2d`; filters by `aggregator`, `original_source`, `tag` |
| **Tag Management** | `/tags` — browse tag groups, review normalization suggestions, merge groups |
| **LLM Providers** | `/admin/llm-providers` — CRUD with priority, rpm/tpm/rpd, is_active toggle |
| **Scraper Config** | Supports RSS, Blog (CSS selector), ArXiv, OpenAlex, Semantic Scholar |
| **Monitoring** | Admin dashboard: OTel traces, Loki logs, OTel metrics, Grafana panels, failed tasks |
| **Auth** | NextAuth v4 with JWT cookies; optional Google OAuth2 |
| **Guest Paywall** | Overlay after 6 articles, redirects to login |
| **i18n** | en + zh-TW; auto-resolves from IP via `/api/languages` |
| **Observability** | Client-side Loki log shipping, OTel OTLP utils, Grafana panel embeds |

## Tech Stack

- **Framework**: Next.js 16 (App Router), React 19, TypeScript
- **Styling**: Tailwind CSS v4, Shadcn/UI (Radix UI primitives), Lucide icons
- **Auth**: NextAuth v4
- **Graph**: react-force-graph-2d
- **Tests**: Vitest + React Testing Library (unit), Playwright (E2E)

## Development

```bash
npm install
npm run dev        # http://localhost:3000
npm run test       # Vitest unit tests
npm run test:e2e   # Playwright E2E tests
```

## Deployment

| Context | File |
|---------|------|
| Production | `Dockerfile` (multi-stage Node build) |
| Development | `Dockerfile.dev` |
| Config | `railway.toml` (Railway service definition) |

Environment variables required: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`. Default port: `3000`.
