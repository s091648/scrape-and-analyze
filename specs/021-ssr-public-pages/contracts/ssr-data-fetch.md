# Contract: Server-Side Data Fetch (`lib/server/ssr-fetch.ts`)

This module is the single place every converted route's `page.tsx` goes through to get its first-paint data. It calls **only existing, unmodified backend endpoints** — this feature introduces no new backend API surface. Documented here as the internal contract between the 4 `page.tsx` Server Components and this shared helper module, since `page.tsx` files must not call `fetch(BACKEND_URL...)` directly (see plan.md's Project Structure — centralizes the credential/topic/language resolution that every route needs identically).

## Exported functions (server-only — never imported from a `'use client'` file)

| Function | Backend endpoint(s) called | Used by |
|---|---|---|
| `resolveSsrContext()` | `GET /topics` and `GET /languages` (only when a NextAuth session exists — see Behavior below) | Called directly by each route's `page.tsx`, once per render (not internal — each `fetchXSSR` below takes the resulting `SsrContext` as a parameter, rather than resolving it itself, so a route needing to override `topicId` from `searchParams` can do so before fetching). |
| `fetchArticlesListSSR(context, searchParams)` | `GET /articles` | `app/articles/page.tsx` |
| `fetchGraphSSR(context, topicId?)` | `GET /analyses/graph` | `app/graph/page.tsx` |
| `fetchTagGroupsSSR(context, topicId?)` | `GET /tag-groups` | `app/tags/page.tsx` |
| `fetchWeeklyReportSSR(context, topicId?)` | `GET /weekly-reports/latest` | `app/page.tsx` |

## Behavior all functions share

1. Resolve credential: reuse `getServerSession(authConfig)`'s `session.accessToken` if present; otherwise `null` — **this feature never calls `POST /auth/guest`** (superseded during implementation; see `research.md`'s credential-resolution decision for why: it would bypass the existing client-side paywall/guest-mode gate for anonymous visitors).
2. If the credential is `null`, every `fetchXSSR` helper below returns `null` immediately without making any backend call — an anonymous visitor's page renders with no server-fetched data, letting the existing client-side paywall/placeholder logic (`isPaywall` checks already present in `articles-page-content.tsx`, `knowledge-graph.tsx`, `tags/page.tsx`) behave exactly as it does today.
3. Otherwise (a session exists): resolve topic (read the `selectedTopicId` cookie; validate against that render's topic list; fall back to no-filter/first-active per `contracts/ssr-preference-cookies.md`) and language (read the `locale` cookie; if absent/invalid, call `GET /languages` with the resolved credential and the visitor's real IP via `X-Forwarded-For`, taken from `headers()`).
4. Call the target endpoint directly against `BACKEND_URL` (not through `/api/proxy/...` — that route exists for *browser*-originated requests; server-to-server calls go straight to the backend, same as `app/api/proxy/[...path]/route.ts` and `lib/auth.ts` already do).
5. On any failure (network error, non-2xx) at any step: catch internally, return `null`. Never throw out of these functions — see `research.md`'s fallback decision and FR-007.

## Non-goals

- No new backend routes, schemas, or auth guards — every endpoint listed above already exists; `POST /auth/guest` specifically is **not** called by this feature at all (see above).
- No change to how `frontend/app/api/proxy/[...path]/route.ts` or client-side `apiFetch()` work — those remain exactly as they are for all post-hydration client requests, including the existing browser-side `sessionStorage` guest-token flow.
