[![frontend unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=frontend-unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=frontend-unit)
![frontend unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-unit-passrate.json)
![frontend e2e tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-e2e-passrate.json)

[![Notion](https://img.shields.io/badge/Storybook-FF4785?logo=storybook&logoColor=white)](https://satisfied-luck-production.up.railway.app/)

# Frontend

Next.js 16 + React 19 web application for browsing AI-analyzed articles, managing scraper sources, and visualizing tag relationships as a knowledge graph.

## Architecture

```
frontend/
├── app/                        # Next.js App Router
│   ├── page.tsx                # Home — article browse entry point
│   ├── layout.tsx              # Root layout + navbar
│   ├── home-page-content.tsx   # Article grid with pagination and filters
│   ├── admin/                  # Admin dashboard
│   ├── graph/                  # Knowledge graph page
│   ├── login/ & register/      # Auth pages
│   ├── settings/               # Scraper source configuration UI
│   └── api/
│       ├── auth/               # NextAuth route handlers
│       ├── link-google/        # Google OAuth2 account linking
│       └── proxy/              # Proxied requests to the backend API
├── components/
│   ├── article-card.tsx        # Article display card (title, preview, source, tags)
│   ├── filter-bar.tsx          # Date range + multi-select source/tag filters
│   ├── knowledge-graph.tsx     # Force-directed graph visualization
│   ├── scraper-source-form.tsx # Form to add RSS / blog / ArXiv scraper sources
│   ├── scraper-source-card.tsx # Display and inline-edit a scraper config
│   ├── arxiv-keyword-manager.tsx # Manage ArXiv search terms
│   ├── nav-bar.tsx             # Header with auth state
│   ├── session-provider.tsx    # NextAuth SessionProvider wrapper
│   └── ui/                     # Shadcn/UI primitives (button, input, modal, etc.)
├── hooks/
│   └── use-pagination.tsx      # Shared pagination + filter state hook
├── lib/
│   └── api-fetch.tsx           # Authenticated HTTP client (attaches JWT)
├── middleware.ts               # NextAuth route protection
├── globals.css                 # Tailwind CSS v4 theme + global styles
├── tests/
│   ├── unit/                   # Vitest + React Testing Library unit tests
│   └── integration/            # Playwright integration tests (full user flows)
│       └── fixtures/           # Auth state, API handlers, token generator
├── vitest.config.ts            # Unit test config (Vitest + React Testing Library)
├── playwright.config.ts        # Integration test config (Playwright)
└── next.config.ts
```

## Key Features

| Feature | Details |
|---------|---------|
| **Article Browse** | Paginated grid (6 cards/page for guests, unlimited for users) |
| **Filtering** | Multi-select sources, tags, and date range (published or scraped date) |
| **Full-text Search** | Passes `q` query param to `/articles` API |
| **Knowledge Graph** | `react-force-graph-2d` force-directed graph of tag and article relationships |
| **Auth** | NextAuth v4 with JWT cookies; optional Google OAuth2 |
| **Guest Paywall** | Overlay after 6 articles, redirects to login |
| **Scraper Config** | Admin panel to add/edit/delete RSS, blog (CSS selector), and ArXiv sources |

## Tech Stack

- **Framework**: Next.js 16 (App Router), React 19, TypeScript
- **Styling**: Tailwind CSS v4, Shadcn/UI (Radix UI primitives), Lucide icons
- **Auth**: NextAuth v4
- **State**: Zustand
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
