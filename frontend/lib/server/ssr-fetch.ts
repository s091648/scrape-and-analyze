// Server-only module — must never be imported from a 'use client' file. Centralizes the
// credential/topic/language resolution every server-rendered route needs identically, plus one
// typed fetch helper per route's first-paint data need. See
// specs/021-ssr-public-pages/contracts/ssr-data-fetch.md and research.md for the design.
//
// Every exported resolver is wrapped in React's `cache()` — within a single request, calling
// e.g. `resolveVisitorTopicAndLocale()` from both `app/layout.tsx` (to seed TopicProvider/
// I18nProvider) and from a page's own `resolveSsrContext()` call resolves to the exact same
// value without a second round-trip: React memoizes by (function, arguments) for the lifetime of
// one render pass, then discards it — this is the standard Next.js App Router pattern for
// "resolve identity/context once per request, use it in many places" (see React docs on `cache`).
// This is what actually fixes 021-ssr-public-pages' post-implementation bug where SSR-seeded
// data was silently discarded: previously, `layout.tsx` had no way to learn what topic a page's
// own `resolveSsrContext()` call had resolved (or vice versa), so TopicProvider's initial state
// and a page's server-fetched data could disagree even within the same request.
//
// Several further optimizations (021-ssr-public-pages, "root cause 1" follow-up — the original
// SSR fetch chain was guest-token -> GET /topics + GET /languages -> the page's own data fetch,
// all sequential, blocking the whole HTML response): `issueOrReuseGuestToken()` caches a guest
// token across many different visitors' requests (guest identity is anonymous, so this is safe);
// `resolveVisitorTopicAndLocale()` skips any backend round trip entirely when both the
// `selectedTopicId` and `locale` cookies already exist (trusts them optimistically instead of
// validating first); and when a backend call *is* needed, `POST /bootstrap` collapses what used
// to be "mint a guest token, then GET /topics + GET /languages" into a single unauthenticated
// round trip (`fetchBootstrap()` below) instead of two serial ones. None of this helps a true
// first-time visitor with no cookie at all — that visitor still needs the one `/bootstrap` round
// trip (nothing else can tell us which topic to default to or which locale to resolve). A full
// multi-device / BFF-aggregation rework that could collapse this further is tracked separately,
// not part of this feature.
//
// Every backend call in this module goes through `ssrFetch()` below — the server-side
// counterpart of `lib/api/client.ts`'s `apiFetch()` — so timeout/abort, credential attachment,
// and retry-on-transient-failure live in one place instead of being hand-rolled per call site.
import { cache } from 'react'
import { cookies, headers } from 'next/headers'
import { getServerSession } from 'next-auth'
import { authConfig } from '@/lib/auth'
import { TOPIC_COOKIE_NAME, LOCALE_COOKIE_NAME } from '@/lib/cookies/constants'
import type { Article } from '@/lib/api/articles'
import type { GraphData } from '@/lib/api/graph'
import type { TagGroupOut } from '@/lib/api/tags'
import type { WeeklyReport } from '@/lib/api/weekly-reports'
import { BACKEND_URL as BACKEND_URL_ENV } from '@/lib/env.server'

const BACKEND_URL = BACKEND_URL_ENV || 'http://localhost:8000'
const SUPPORTED_LANGUAGE_CODES = ['en', 'zh-TW']
// Every backend call in this module runs on the SSR request path and blocks the HTML
// response — Node's fetch has no default timeout, so a backend that accepts the TCP
// connection but never responds would otherwise hang the render until the platform
// kills it. AbortSignal.timeout() raises, so ssrFetch's own catch (and every caller's
// existing try/catch) already produce the correct degraded (null/'en') result.
const SSR_FETCH_TIMEOUT_MS = 3_000
// Retries are deliberately minimal — unlike lib/api/client.ts's apiFetch (background UI
// fetches, MAX_ATTEMPTS=4), every attempt here blocks the HTML response, so this trades a
// little resilience to a transient backend hiccup against not stalling the page load too long.
const SSR_MAX_ATTEMPTS = 2
const SSR_RETRY_DELAY_MS = 150
// selectedTopicId is a plain client-writable cookie (see resolveVisitorTopicAndLocale's
// comment on why it's trusted without a /bootstrap round trip) — this only guards its
// shape before it's interpolated into a backend query string, not its validity.
const TOPIC_ID_PATTERN = /^[0-9a-fA-F-]{1,64}$/

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function isRetryableStatus(status: number): boolean {
  return status === 429 || status >= 500
}

/** Plain object (not a `Headers` instance) — every call site here builds its own headers from
 * scratch rather than forwarding a caller-supplied Authorization, so the extra normalization a
 * `Headers` instance gives lib/api/client.ts's apiFetch isn't needed on this path. */
function buildSsrHeaders(init: RequestInit, credential?: string | null): Record<string, string> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) }
  if (credential) headers.Authorization = `Bearer ${credential}`
  return headers
}

/** Shared request layer for every backend call in this module — the server-side counterpart of
 * lib/api/client.ts's `apiFetch()`. Attaches the bearer credential (if given), bounds each
 * attempt to `timeoutMs` (default `SSR_FETCH_TIMEOUT_MS`), and retries once on a network
 * failure or a 429/5xx before giving up (`SSR_MAX_ATTEMPTS`). Returns `null` only when every
 * attempt threw (timeout or network failure); a non-ok Response is returned as-is so each
 * caller keeps deciding for itself what "not ok" means for its own endpoint. Never throws. */
async function ssrFetch(
  url: string,
  init: RequestInit = {},
  options: { credential?: string | null; timeoutMs?: number } = {},
): Promise<Response | null> {
  const requestHeaders = buildSsrHeaders(init, options.credential)
  const timeoutMs = options.timeoutMs ?? SSR_FETCH_TIMEOUT_MS
  for (let attempt = 0; attempt < SSR_MAX_ATTEMPTS; attempt++) {
    const isLastAttempt = attempt === SSR_MAX_ATTEMPTS - 1
    try {
      const res = await fetch(url, {
        ...init,
        headers: requestHeaders,
        signal: AbortSignal.timeout(timeoutMs),
      })
      if (res.ok || !isRetryableStatus(res.status) || isLastAttempt) return res
    } catch {
      if (isLastAttempt) return null
    }
    await sleep(SSR_RETRY_DELAY_MS)
  }
  return null
}

export interface SsrContext {
  /** Bearer token for this render's backend calls — the visitor's reused NextAuth session token,
   * or (only when `resolveSsrContext({ allowGuestCredential: true })` is explicitly requested) a
   * one-time guest token from `POST /auth/guest`. `null` when neither could be obtained.
   *
   * `allowGuestCredential` defaults to `false` and MUST stay that way for `/articles`, `/graph`,
   * and `/tags` — those pages' client-side code deliberately withholds real content
   * (`isPaywall` checks) from a visitor who is neither authenticated nor has opted into guest
   * mode (a `sessionStorage`-only flag with no server-visible equivalent); fetching real data
   * server-side for such a visitor would silently bypass that paywall. `/` (home) has no such
   * gate — `weekly-report-widget.tsx` shows the latest report to every visitor regardless of
   * auth state — so it opts into `allowGuestCredential: true` to get the same SSR benefit
   * anonymous visitors would otherwise miss entirely. This flag ONLY affects whether *this*
   * page's own real-data fetch is allowed to run for an anonymous visitor — it is unrelated to
   * `topicId`/`locale` below, which are always resolved (see `resolveVisitorTopicAndLocale`),
   * since knowing "which topic tab is selected" isn't sensitive/paywalled content by itself. */
  credential: string | null
  /** Resolved from the `selectedTopicId` cookie if present (trusted optimistically, NOT validated
   * against a live topic list — see `resolveVisitorTopicAndLocale`'s comment for why), else the
   * first topic from `POST /bootstrap` (matching `topic-provider.tsx`'s own no-stored-preference
   * default) — or `null` if there are no topics at all. Always resolved (via
   * `resolveVisitorTopicAndLocale`, shared with `app/layout.tsx`), independent of whether
   * `credential` above is null. */
  topicId: string | null
  /** Resolved from the `locale` cookie, or geo-IP via `POST /bootstrap` when absent/unsupported.
   * Always resolved, independent of `credential` — see `topicId` above. */
  locale: string
}

// Module-level (NOT per-request `cache()`) — the frontend/frontend_prod containers run Next.js
// as a long-lived Node process (docker-compose.yml, `npx next start`), not serverless, so a
// plain module variable persists across many different visitors' requests for that process's
// lifetime. Guest tokens are anonymous (never tied to a specific visitor), so reusing one across
// unrelated visitors' SSR renders is safe and eliminates the `POST /auth/guest` round trip for
// the vast majority of anonymous SSR renders — previously every single anonymous render paid for
// its own fresh token. `fetchBootstrap()` below also opportunistically populates this same cache
// from `POST /bootstrap`'s own minted token (that endpoint always mints one, whether or not the
// caller ends up using it) — a plain unconditional overwrite, since guest tokens are anonymous
// and interchangeable, so there's no "wrong" token to protect against clobbering. A benign race
// (two concurrent requests both seeing an expired/absent cache and each issuing their own token)
// is possible right at cold-start/expiry and is left unguarded — it costs one extra token mint,
// not a correctness issue. If this frontend
// ever scales to multiple replicas, each replica keeps its own independent cache — still a large
// win over no caching, though not perfectly shared; moving this to the existing Redis
// (`CACHE_REDIS_URL`, from 020-redis-caching-layer) would be the next step if that matters.
let cachedGuestToken: { token: string; expiresAt: number } | null = null
const GUEST_TOKEN_REFRESH_MARGIN_MS = 60_000 // mirrors auth-token-provider.tsx's client-side margin

/** Test-only: clears the module-level guest-token cache so test cases don't leak state into
 * each other (tests import and call this in `beforeEach`; not used by application code). */
export function __resetGuestTokenCacheForTests(): void {
  cachedGuestToken = null
}

async function issueOrReuseGuestToken(): Promise<string | null> {
  if (cachedGuestToken && cachedGuestToken.expiresAt - GUEST_TOKEN_REFRESH_MARGIN_MS > Date.now()) {
    return cachedGuestToken.token
  }
  try {
    const res = await ssrFetch(`${BACKEND_URL}/auth/guest`, { method: 'POST' })
    if (!res?.ok) return null
    const data = await res.json()
    if (typeof data.access_token !== 'string') return null
    const expiresInMs = typeof data.expires_in === 'number' ? data.expires_in * 1000 : 3600_000
    cachedGuestToken = { token: data.access_token, expiresAt: Date.now() + expiresInMs }
    return cachedGuestToken.token
  } catch {
    return null
  }
}

const resolveCredential = cache(async (allowGuestCredential: boolean): Promise<string | null> => {
  try {
    const session = await getServerSession(authConfig)
    const sessionToken = (session as { accessToken?: string } | null)?.accessToken
    if (sessionToken) return sessionToken
  } catch {
    // Fall through — a session lookup failure shouldn't take down the render.
  }

  if (!allowGuestCredential) return null
  return issueOrReuseGuestToken()
})

/** Calls the unauthenticated `POST /bootstrap` (no credential needed — see that endpoint's own
 * doc comment) to resolve a default topic + locale in one round trip, and opportunistically
 * feeds its always-minted guest token into `cachedGuestToken` (see that variable's doc comment).
 * Never throws — degrades to `{ topicId: null, locale: 'en' }` on any failure, matching the
 * degraded defaults `resolveVisitorTopicAndLocale` promises below. */
async function fetchBootstrap(): Promise<{ topicId: string | null; locale: string }> {
  try {
    const headerStore = await headers()
    const forwardedFor = headerStore.get('x-forwarded-for')
    const res = await ssrFetch(`${BACKEND_URL}/bootstrap`, {
      method: 'POST',
      headers: forwardedFor ? { 'X-Forwarded-For': forwardedFor } : {},
    })
    if (!res?.ok) return { topicId: null, locale: 'en' }
    const data = await res.json()
    if (typeof data.access_token === 'string') {
      const expiresInMs = typeof data.expires_in === 'number' ? data.expires_in * 1000 : 3600_000
      cachedGuestToken = { token: data.access_token, expiresAt: Date.now() + expiresInMs }
    }
    const topics = Array.isArray(data.topics) ? data.topics : []
    // Mirrors topic-provider.tsx's loadTopics() default for a visitor with no stored preference:
    // no preference at all → first topic, not "no filter".
    const topicId = typeof topics[0]?.id === 'string' ? topics[0].id : null
    const locale = typeof data.languages?.resolved === 'string' ? data.languages.resolved : 'en'
    return { topicId, locale }
  } catch {
    return { topicId: null, locale: 'en' }
  }
}

/** Resolves the visitor's topic/language for this request — never throws, degrades to
 * `{ topicId: null, locale: 'en' }` on failure, per FR-007. Independent of `resolveSsrContext`'s
 * own `credential` (which stays paywall-aware per caller) since knowing which topic tab is
 * selected isn't sensitive/paywalled content.
 *
 * `cache()`-wrapped with no arguments, so every caller within one request — `app/layout.tsx`
 * (seeding TopicProvider/I18nProvider) and every page's own `resolveSsrContext()` call below —
 * shares one resolution. This is what keeps them from disagreeing with each other. */
export const resolveVisitorTopicAndLocale = cache(async (): Promise<{ topicId: string | null; locale: string }> => {
  const cookieStore = await cookies()
  const cookieTopicId = cookieStore.get(TOPIC_COOKIE_NAME)?.value
  const cookieLocale = cookieStore.get(LOCALE_COOKIE_NAME)?.value
  // Optimistic trust: a cookie already naming a topic/locale is used directly, without
  // validation — this is what actually collapses the SSR fetch chain for returning visitors. A
  // topicId cookie naming a topic that's since been deleted/deactivated is trusted anyway; that
  // one render's data fetch (weekly-report/articles/graph/tags) just comes back empty for it,
  // exactly like today's "nothing found" fallback — topic-provider.tsx's own client-side
  // `loadTopics()` validation (unchanged) corrects both the in-memory state and the cookie on its
  // next run, so this self-heals within one visit. See specs/021-ssr-public-pages research.md's
  // root-cause-1 follow-up. Still shape/allowlist-checked (TOPIC_ID_PATTERN /
  // SUPPORTED_LANGUAGE_CODES) before being trusted — both cookies are client-writable, and
  // topicId flows straight into backend query strings elsewhere in this module.
  const topicIdFromCookie = cookieTopicId && TOPIC_ID_PATTERN.test(cookieTopicId) ? cookieTopicId : null
  const localeFromCookie = cookieLocale && SUPPORTED_LANGUAGE_CODES.includes(cookieLocale) ? cookieLocale : null

  // Both already known — skip the /bootstrap round trip entirely (returning visitor).
  if (topicIdFromCookie && localeFromCookie) {
    return { topicId: topicIdFromCookie, locale: localeFromCookie }
  }

  // At least one is missing (true first-time visitor, or only one of the two cookies is set) —
  // /bootstrap resolves both at once; whichever one was already known from a cookie takes
  // priority over its bootstrap-resolved counterpart.
  const bootstrap = await fetchBootstrap()
  return {
    topicId: topicIdFromCookie ?? bootstrap.topicId,
    locale: localeFromCookie ?? bootstrap.locale,
  }
})

/** Resolves this render's full context: a paywall-aware `credential` (see `SsrContext`'s doc
 * comment) plus the shared, always-on `topicId`/`locale` from `resolveVisitorTopicAndLocale`.
 * Never throws.
 *
 * @param options.allowGuestCredential See `SsrContext.credential`'s doc comment — leave this
 * `false` (the default) for any paywalled route (`/articles`, `/graph`, `/tags`); only `/` (home)
 * should pass `true`. */
export async function resolveSsrContext(
  options: { allowGuestCredential?: boolean } = {},
): Promise<SsrContext> {
  const [credential, { topicId, locale }] = await Promise.all([
    resolveCredential(options.allowGuestCredential ?? false),
    resolveVisitorTopicAndLocale(),
  ])
  return { credential, topicId, locale }
}

/** Wraps an SSR-fetched value with the backend's `X-Cache` status (HIT/MISS/BYPASS). Every call in
 * this module runs server-to-server, so that header never reaches the browser on its own — callers
 * surface `cacheStatus` into the rendered page (e.g. a hidden `data-` attribute) instead, purely as
 * a debugging aid for verifying cache effectiveness (020-redis-caching-layer). `null` means the
 * fetch never actually reached the backend (no credential, or a caught failure) — see each
 * `fetchXxxSSR` function's own early-return paths — not a real cache outcome. */
export interface SsrCachedResult<T> {
  value: T
  cacheStatus: string | null
}

export async function fetchArticlesListSSR(
  context: SsrContext,
  searchParams: URLSearchParams,
): Promise<SsrCachedResult<{ items: Article[]; total: number }> | null> {
  if (!context.credential) return null
  try {
    const qs = new URLSearchParams(searchParams)
    if (context.topicId && !qs.has('topic_id')) qs.set('topic_id', context.topicId)
    const separator = qs.toString() ? '&' : ''
    const res = await ssrFetch(
      `${BACKEND_URL}/articles?${qs.toString()}${separator}lang=${context.locale}`,
      {},
      { credential: context.credential },
    )
    if (!res?.ok) return null
    return { value: await res.json(), cacheStatus: res.headers.get('X-Cache') }
  } catch {
    return null
  }
}

export async function fetchGraphSSR(
  context: SsrContext,
  topicIdOverride?: string | null,
): Promise<SsrCachedResult<GraphData> | null> {
  const topicId = topicIdOverride ?? context.topicId
  if (!context.credential || !topicId) return null
  try {
    // Matches KnowledgeGraph's own default filter (components/features/graph/knowledge-graph.tsx)
    // so the seeded data is identical to what a fresh client fetch would have produced.
    const publishedAfter = new Date()
    publishedAfter.setDate(publishedAfter.getDate() - 30)
    const qs = new URLSearchParams({
      topic_id: topicId,
      lang: context.locale,
      published_after: publishedAfter.toISOString().slice(0, 10),
    })
    const res = await ssrFetch(
      `${BACKEND_URL}/analyses/graph?${qs.toString()}`,
      {},
      { credential: context.credential },
    )
    if (!res?.ok) return null
    return { value: await res.json(), cacheStatus: res.headers.get('X-Cache') }
  } catch {
    return null
  }
}

export async function fetchTagGroupsSSR(
  context: SsrContext,
  topicIdOverride?: string | null,
): Promise<SsrCachedResult<TagGroupOut[]> | null> {
  const topicId = topicIdOverride ?? context.topicId
  if (!context.credential) return null
  try {
    const qs = topicId ? `?${new URLSearchParams({ topic_id: topicId }).toString()}` : ''
    const res = await ssrFetch(`${BACKEND_URL}/tag-groups${qs}`, {}, { credential: context.credential })
    if (!res?.ok) return null
    return { value: await res.json(), cacheStatus: res.headers.get('X-Cache') }
  } catch {
    return null
  }
}

export async function fetchWeeklyReportSSR(
  context: SsrContext,
  topicIdOverride?: string | null,
): Promise<SsrCachedResult<WeeklyReport> | null> {
  const topicId = topicIdOverride ?? context.topicId
  if (!context.credential || !topicId) return null
  try {
    const qs = new URLSearchParams({ topic_id: topicId, lang: context.locale })
    const res = await ssrFetch(
      `${BACKEND_URL}/weekly-reports/latest?${qs.toString()}`,
      {},
      { credential: context.credential },
    )
    if (!res?.ok) return null
    return { value: await res.json(), cacheStatus: res.headers.get('X-Cache') }
  } catch {
    return null
  }
}
