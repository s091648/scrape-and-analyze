# Implementation Plan: SSR Conversion for Public Pages (LCP Fix)

**Branch**: `020-redis-caching-layer` (reused, see spec Assumptions) | **Date**: 2026-08-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/021-ssr-public-pages/spec.md`

## Summary

Convert `/`, `/articles`, `/graph`, and `/tags` from pure client-side rendering to server-rendered first paint, so the article/graph/tag content that currently only appears after JS-bundle-download → hydrate → two sequential client fetches is instead present in the initial HTML response — **for authenticated visitors**. Each route's `page.tsx` becomes an `async` Server Component that, when a NextAuth session exists, fetches its default-state data directly from the backend (via the existing server-only `BACKEND_URL`, the same mechanism `app/api/proxy/[...path]/route.ts` already uses) and passes it as initial props to the existing (now-renamed, otherwise largely unchanged) client content component, which hydrates from that data instead of starting from an empty/loading state and re-fetching. Two new visitor-preference cookies (`selectedTopicId`, `locale`) let the server resolve the same topic/language a returning authenticated visitor already chose, mirroring the existing `localStorage` values so first paint doesn't need a post-hydration correction. **Anonymous visitors are deliberately excluded from server-side data fetching** (a correction made mid-implementation, see spec.md User Story 3 and research.md): every converted page already withholds real content client-side from a visitor who is neither logged in nor has opted into "Continue as Guest" (a `sessionStorage`-only flag invisible to the server), so the server instead renders the same static placeholder/paywall state for that visitor — fast, but unchanged in content from today. This directly capitalizes on 020's Redis cache-aside + eager warm-up layer for the authenticated-visitor path: these are exactly the default-parameter reads `CacheWarmupHandler` already keeps warm, so the new server-side fetches should mostly be cache hits.

## Technical Context

**Language/Version**: TypeScript (strict mode), Next.js 16 App Router, React 19. No backend (`backend/`) or scraper (`src/`) code changes — this is purely a `frontend/` architecture change consuming existing, unmodified backend endpoints.

**Primary Dependencies**: Next.js `cookies()`/`headers()` APIs (Server Component data access), NextAuth v4 (`getServerSession` — already used server-side in `app/admin/monitoring/page.tsx`, but that page's "redirect if unauthenticated" pattern doesn't apply here; this feature needs the "render content even if unauthenticated" pattern which has no existing precedent in this codebase), existing `fetch` (server-side, direct to `BACKEND_URL`, no new HTTP client dependency).

**Storage**: N/A — no database or Redis changes. Consumes the existing Redis cache-aside layer built in `020-redis-caching-layer` (`shared/cache/`) indirectly, via the backend endpoints it already fronts.

**Testing**: Vitest for the new Server Components' data-fetching logic (mockable `fetch`), Playwright E2E for the actual SSR behavior (page loaded with JS disabled/before hydration must contain real content — Playwright can assert on the raw HTML response body before any client JS runs), per Constitution Principle III's mandatory test-phase requirement (`frontend/tests/unit/`, `frontend/tests/integration/`).

**Target Platform**: Same as existing frontend — Next.js server running in Docker (`frontend` dev service, `frontend_prod` production-parity service per 020's Phase 8 addition, and Railway in production).

**Project Type**: Web application (existing `backend/` + `frontend/` + `src/` structure; this feature touches `frontend/` only).

**Performance Goals**: LCP under 2.5s ("Good" Core Web Vitals threshold) for a first-time, cold-cache visit to `/` and `/articles`, measured via `frontend_prod` (production build), per spec SC-001.

**Constraints**: No duplicate first-paint-content fetch between server and client (spec SC-004) — the client must hydrate from server-provided data, not re-fetch the same default query on mount. No new backend endpoints or auth model changes (spec Assumptions — guest identity redesign is explicitly out of scope). Cookie-based preferences (topic, language) must degrade gracefully to today's defaults when absent (first-ever visit).

**Scale/Scope**: 4 routes converted (`/`, `/articles`, `/graph`, `/tags`), 2 new cookies, 1 new server-side data-fetch utility module reused across all 4 routes' `page.tsx` files. No new pages, no new backend surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle II (Atomic Frontend Architecture)** — PASS. This feature *is* the `page.tsx`/`xxx-page-content.tsx` split described in CLAUDE.md, applied to 4 routes (2 that already have it — `page.tsx`/`home-page-content.tsx`, `page.tsx`/`articles-page-content.tsx` — gain server-fetching logic in the existing `page.tsx`; 2 that don't yet — `app/graph/page.tsx`, `app/tags/page.tsx` — gain the split for the first time, per FR-009). No new component directories; existing `components/features/{articles,graph,tags}/*` are reused as-is, only their initial data source changes (props instead of empty state + effect).
- **Principle III (Test Discipline)** — PASS, with a new test surface: Playwright E2E gets its first assertions on raw pre-hydration HTML content (`frontend/tests/integration/`), and Vitest unit-tests the new server-side fetch helper module in isolation (mocked `fetch`, mocked `cookies()`/`headers()`). Mandatory test phase will be included in `tasks.md` per the constitution's explicit override of the tasks-template's "tests are optional" language.
- **Principle IV (Docker-First Local Development)** — PASS. No new services. Reuses `020-redis-caching-layer`'s `frontend_prod` (`profile: tools`) for production-parity LCP measurement — dev-server numbers are explicitly not representative (per that spec's Phase 8 note) and SC-001 must be measured there.
- **Principle VII (Code Style)** — PASS. TypeScript strict mode, i18n via `I18nProvider`/locale files unaffected in shape (only the *initial* resolution mechanism changes, not the translation system itself).
- No DDD (`src/`) or FastAPI microservice (Principle I, IX) impact — no backend code changes.

No violations requiring Complexity Tracking.

**Post-Design Re-Check** (after Phase 1): The two new cookies (`data-model.md`), the single new server-only module (`lib/server/ssr-fetch.ts`), and the new Route Handler for cookie writes introduce no new component-boundary, testing, Docker, or code-style concerns beyond what was already assessed above — no principle re-evaluation needed.

## Project Structure

### Documentation (this feature)

```text
specs/021-ssr-public-pages/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── ssr-preference-cookies.md
│   └── ssr-data-fetch.md
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this command)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── page.tsx                        # MODIFIED: becomes async Server Component, fetches default-state
│   │                                    #   data via lib/server/ssr-fetch.ts, passes as props
│   ├── home-page-content.tsx           # MODIFIED: accepts initial props instead of fetching internally
│   ├── articles/
│   │   ├── page.tsx                    # MODIFIED: async Server Component; searchParams becomes a
│   │   │                                #   Next.js prop (Promise<SearchParams> per Next 15+ convention)
│   │   │                                #   instead of a client useSearchParams() hook, passed through
│   │   │                                #   alongside server-fetched default-page data
│   │   └── articles-page-content.tsx   # MODIFIED: accepts initial articles/total as props; effect only
│   │                                    #   re-fetches on filter/page CHANGE, not on mount when initial
│   │                                    #   data already matches current params
│   ├── graph/
│   │   └── page.tsx                    # MODIFIED: split into async Server Component (fetches
│   │                                    #   /analyses/graph default) + graph-page-content.tsx (NEW)
│   └── tags/
│       └── page.tsx                    # MODIFIED: split into async Server Component (fetches
│                                        #   /tag-groups default) + tags-page-content.tsx (NEW)
├── lib/
│   ├── cookies/
│   │   ├── constants.ts                # NEW: isomorphic — cookie names (`selectedTopicId`, `locale`)
│   │   │                                #   + shared Max-Age, importable from both client and server code
│   │   └── set-preference-cookie.ts    # NEW: client-only helper, writes via `document.cookie` directly
│   │                                    #   (both cookies are non-httpOnly, so no Route Handler/Server
│   │                                    #   Action round-trip is needed just to set them)
│   ├── server/
│   │   └── ssr-fetch.ts                # NEW: server-only module — obtains a one-time guest credential
│   │                                    #   (calls BACKEND_URL POST /auth/guest) when no NextAuth
│   │                                    #   session exists, resolves topic (cookie via `next/headers`
│   │                                    #   `cookies()`) and language (cookie, else BACKEND_URL
│   │                                    #   GET /languages via the credential), and exposes typed
│   │                                    #   fetchArticlesListSSR/fetchGraphSSR/fetchTagGroupsSSR/
│   │                                    #   fetchWeeklyReportSSR helpers. Never imported from a
│   │                                    #   'use client' file.
│   └── providers/
│       └── topic-provider.tsx          # MODIFIED: setSelectedTopicId calls set-preference-cookie.ts
│                                        #   in addition to its existing localStorage.setItem; initial
│                                        #   state can be seeded from a prop (see data-model.md) instead
│                                        #   of always starting null
└── tests/
    ├── unit/
    │   └── lib/server/ssr-fetch.test.ts       # NEW
    └── integration/
        └── ssr-first-paint.spec.ts             # NEW (Playwright)
```

**Structure Decision**: Existing `frontend/app/*/page.tsx` + `*-page-content.tsx` split (already documented in CLAUDE.md) is extended to `/graph` and `/tags`, which currently lack it. All server-only logic is centralized in one new module (`lib/server/ssr-fetch.ts`) rather than duplicated per-route, since all 4 routes need the identical guest-credential + topic/language-cookie resolution sequence before their route-specific fetch. No new top-level directories.

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*
