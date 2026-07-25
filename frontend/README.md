[![frontend unit coverage](https://codecov.io/gh/s091648/scrape-and-analyze/graph/badge.svg?token=RADSEJRK64&flag=frontend-unit)](https://codecov.io/gh/s091648/scrape-and-analyze?flag=frontend-unit)
![frontend unit tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-unit-passrate.json)
![frontend e2e tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/s091648/ca46ff0f1130f4b6e02d2ed6ea0ed243/raw/frontend-e2e-passrate.json)

[![Notion](https://img.shields.io/badge/Storybook-FF4785?logo=storybook&logoColor=white)](https://satisfied-luck-production.up.railway.app/)

# Frontend

Next.js 16 + React 19 web application for browsing AI-analyzed articles, chatting with a RAG-powered assistant, managing scraper sources, visualizing tag relationships as a knowledge graph, and administering LLM providers.

## Architecture

```
frontend/
├── app/                              # Next.js App Router
│   ├── page.tsx                      # Home — article browse entry point
│   ├── layout.tsx                    # Root layout (providers, ErrorBoundary, NavBar)
│   ├── layout-shell.tsx              # Inner shell
│   ├── articles/
│   │   ├── page.tsx                  # Article browse (guest paywall applies here)
│   │   └── [articleId]/page.tsx      # Full article detail page
│   ├── tags/page.tsx                 # Tag browser + normalization suggestions
│   ├── graph/page.tsx                # Knowledge graph visualization
│   ├── login/ & register/            # Auth pages
│   ├── settings/                     # User-facing scraper source config + notification prefs
│   │   ├── page.tsx & settings-page-content.tsx
│   │   └── notifications/
│   ├── admin/
│   │   ├── llm-providers/page.tsx        # LLM provider CRUD (priority, rpm/tpm/rpd, is_active)
│   │   ├── metric-definitions/page.tsx   # Metric catalog display config (icon, enabled)
│   │   ├── monitoring/                   # Observability dashboard (traces, logs, metrics, Grafana)
│   │   ├── scraper-settings/             # RSS / blog / ArXiv / OpenAlex / Semantic Scholar sources
│   │   ├── topics/                       # Topic management
│   │   └── user-management/              # User admin
│   └── api/
│       ├── auth/[[...nextauth]]/     # NextAuth route handlers
│       ├── proxy/[...path]/          # Catch-all reverse proxy → backend:8000
│       ├── grafana-embed/            # Grafana panel embed proxy (signed URLs)
│       └── link-google/              # Google OAuth2 account linking (start + callback)
├── components/
│   ├── common/                       # Reusable primitives (date-filter, error-boundary, multi-select-popover)
│   ├── features/
│   │   ├── articles/                 # Article card, detail dialog, filter bar, grouped tag select
│   │   ├── chat/                     # FloatingChatbotPanel/Wrapper, InlineQABarWrapper, AnswerDisplay,
│   │   │                             #   cited-content — RAG chat UI (talks to /chat/completions)
│   │   ├── graph/                    # Force-directed knowledge graph
│   │   ├── monitoring/               # Trace/log/metric dashboards, failed-task list, Grafana panel embed
│   │   ├── navigation/                # Nav bar, release notes popover
│   │   ├── scraper/                  # Scraper source form/card, keyword managers (ArXiv/OpenAlex/S2)
│   │   ├── settings/                 # Notification settings helpers (e.g. Telegram chat-id guide)
│   │   ├── tags/                     # Merge/tag dialogs, pending-changes review
│   │   ├── tutorial/                 # Guided-tour overlay + registry
│   │   └── weekly-report/            # Weekly report widget, stepper, skeleton
│   └── ui/                           # Shadcn/UI primitives (button, card, dialog, table, etc.)
├── hooks/
│   └── use-pagination.ts             # Shared pagination + filter state hook
├── lib/
│   ├── api/                          # Typed API client modules (one per backend router) — see below
│   ├── providers/                    # React context providers — see Auth Flow below
│   ├── auth.ts                       # NextAuth config (JWT, Google providers)
│   ├── auth-token-store.ts           # Module-level bearer-token store apiFetch() reads from
│   ├── chat-session.ts               # Chat session/thread state helpers
│   ├── loki-logger.ts                # Client-side Loki log shipping
│   ├── observability-constants.ts    # Shared OTel attribute names
│   ├── otlp-utils.ts                 # OTel trace/metric helpers
│   └── utils.ts                      # General utilities (cn, etc.)
├── instrumentation-client.ts         # Sentry browser SDK init (runs before all other client code)
├── middleware.ts                     # Route matcher for /admin/* — currently a no-op; /admin/*
│                                      #   protection is enforced client-side via useSession() instead
├── globals.css                       # Tailwind CSS v4 theme + global styles
├── tests/
│   ├── unit/                         # Vitest + React Testing Library (~90 test files)
│   └── integration/                  # Playwright E2E
│       └── fixtures/                 # Auth state, API handlers, token generator
├── __tests__/api/                    # Next.js API route unit tests (proxy redaction, grafana-embed)
├── vitest.config.ts
└── playwright.config.ts
```

## Key Features

| Feature | Details |
|---------|---------|
| **Article Browse** | Paginated grid; guest paywall overlay after a limited number of cards |
| **Article Detail** | Full detail page at `/articles/[articleId]` |
| **Filtering** | Multi-select: sources, aggregators, original_sources, tags, date range |
| **RAG Chat** | Floating chatbot panel + inline Q&A bar; streams from `/chat/completions` (proxied to `chatbot-plugin`), including tool-call and citation events |
| **Knowledge Graph** | `react-force-graph-2d`; filters by `aggregator`, `original_source`, `tag` |
| **Tag Management** | `/tags` — browse tag groups, review normalization suggestions, merge groups |
| **LLM Providers** | `/admin/llm-providers` — CRUD with priority, rpm/tpm/rpd, is_active toggle (DB-driven, no config file) |
| **Metric Definitions** | `/admin/metric-definitions` — toggle which citation-count-style metrics are shown, and their icon |
| **Scraper Config** | Supports RSS, Blog (CSS selector), ArXiv, OpenAlex, Semantic Scholar |
| **Monitoring** | Admin dashboard: OTel traces, Loki logs, OTel metrics, Grafana panels, failed tasks |
| **Auth** | NextAuth v4 with JWT cookies; optional Google OAuth2; transparent guest-token bootstrap for anonymous visitors (no login required to browse) |
| **Guest Mode** | Paywall overlay + guided tutorial framing for anonymous visitors, independent of the guest *token* plumbing (see Auth Flow) |
| **i18n** | en + zh-TW; auto-resolves from IP via `/api/languages` |
| **Observability** | Client-side Loki log shipping, Sentry browser error tracking, OTel OTLP utils, Grafana panel embeds |

## Auth Flow

Two providers exist in `lib/providers/` and serve different concerns — neither replaced the other:

- **`auth-token-provider.tsx`** (`AuthTokenProvider`/`useAuthToken`) resolves whichever bearer token should be sent with backend requests: the real NextAuth session token when logged in, otherwise a guest access token it acquires via `POST /auth/guest` and silently refreshes via `POST /auth/guest/refresh` (cached in `sessionStorage`). It writes the resolved token into `lib/auth-token-store.ts`, which `apiFetch()` (`lib/api/client.ts`) reads synchronously and attaches as `Authorization: Bearer <token>` to every call that doesn't already set its own header. This is what keeps previously-public endpoints working transparently now that the backend requires a token on nearly everything.
- **`guest-mode-provider.tsx`** (`GuestModeProvider`/`useGuestMode`) is unrelated UI/UX state — whether the visitor has opted into the guest browsing experience (paywall overlay, guided tutorial framing), stored in `sessionStorage` and auto-exited once a real session exists. It has no knowledge of tokens.

`apiFetch()` also redirects to `/login` on a `401` when a real session exists, shows a toast (`sonner`) on any non-ok response (opt out per call with `{ silent: true }`), and reports `5xx` responses to Sentry.

## Tech Stack

- **Framework**: Next.js 16, React 19, TypeScript
- **Styling**: Tailwind CSS v4, Shadcn/UI (Radix UI primitives), Lucide icons
- **Auth**: NextAuth v4 + a custom guest-token layer (see above)
- **Graph**: react-force-graph-2d
- **Observability**: `@sentry/browser`, custom Loki log shipping, OTel OTLP utils
- **Tests**: Vitest + React Testing Library (unit), Playwright (E2E), Storybook (component catalog)

## Development

```bash
npm install
npm run dev            # http://localhost:3000
npm run test            # Vitest unit tests
npm run test:coverage
npm run test:e2e        # Playwright E2E
npm run storybook       # Component catalog on :6006
npm run lint
npm run format
```

## Deployment

| Context | File |
|---------|------|
| Production | `Dockerfile` (multi-stage Node build) |
| Development | `Dockerfile.dev` |
| Config | `railway.toml` (Railway service definition) |

Deployed via this monorepo's CI (`railway up` — staging on PR, production on version tag; see the root `.specify/memory/constitution.md` Principle V), not Railway's own branch-watch auto-deploy.

Environment variables required: `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `NEXT_PUBLIC_API_URL`. Optional: `SENTRY_DSN` (shared with the backend, exposed via `next.config.ts`'s `env`). Default port: `3000`.
