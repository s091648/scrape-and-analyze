import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGetServerSession } = vi.hoisted(() => ({ mockGetServerSession: vi.fn() }))
vi.mock('next-auth', () => ({ getServerSession: mockGetServerSession }))
vi.mock('@/lib/auth', () => ({ authConfig: {} }))

const { mockCookiesGet, mockHeadersGet } = vi.hoisted(() => ({
  mockCookiesGet: vi.fn(),
  mockHeadersGet: vi.fn(),
}))
vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({ get: mockCookiesGet })),
  headers: vi.fn(async () => ({ get: mockHeadersGet })),
}))

import {
  resolveSsrContext,
  fetchArticlesListSSR,
  fetchGraphSSR,
  fetchTagGroupsSSR,
  fetchWeeklyReportSSR,
  __resetGuestTokenCacheForTests,
  type SsrContext,
} from '@/lib/server/ssr-fetch'

function jsonResponse(body: unknown, ok = true, cacheStatus: string | null = null): Response {
  return {
    ok,
    json: async () => body,
    headers: { get: (name: string) => (name === 'X-Cache' ? cacheStatus : null) },
  } as unknown as Response
}

const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
  mockCookiesGet.mockReturnValue(undefined)
  mockHeadersGet.mockReturnValue(null)
  mockGetServerSession.mockResolvedValue(null)
  // The module-level guest-token cache (research.md's root-cause-1 follow-up) persists across
  // requests by design — but that means it'd also leak across test cases in this same file
  // unless explicitly reset.
  __resetGuestTokenCacheForTests()
})

describe('resolveSsrContext — credential resolution', () => {
  it('reuses the NextAuth session token when a session exists', async () => {
    mockGetServerSession.mockResolvedValue({ accessToken: 'session-jwt' })
    fetchMock.mockResolvedValue(jsonResponse([]))
    const ctx = await resolveSsrContext()
    expect(ctx.credential).toBe('session-jwt')
  })

  // No session, allowGuestCredential defaulted to false → the *page's* credential (used for
  // this page's own real-data fetch) stays null — POST /auth/guest is never called *for that
  // purpose*, since doing so would bypass the paywall on /articles, /graph, /tags (see
  // SsrContext's doc comment). Note this is now independent of topic/locale resolution below,
  // which always uses its own internal guest fallback regardless of this page-level setting.
  it('resolves a null page credential when there is no session and allowGuestCredential is not set', async () => {
    mockGetServerSession.mockResolvedValue(null)
    fetchMock.mockResolvedValue(jsonResponse([]))
    const ctx = await resolveSsrContext()
    expect(ctx.credential).toBeNull()
  })

  it('resolves a null page credential when getServerSession itself throws and allowGuestCredential is not set', async () => {
    mockGetServerSession.mockRejectedValue(new Error('session lookup failed'))
    fetchMock.mockResolvedValue(jsonResponse([]))
    const ctx = await resolveSsrContext()
    expect(ctx.credential).toBeNull()
  })

  // topicId/locale are resolved via resolveVisitorTopicAndLocale's own internal guest-credential
  // fallback — always, regardless of the calling page's allowGuestCredential setting — since
  // knowing "which topic is selected" isn't paywalled content (see module doc comment). This is
  // what lets app/layout.tsx and every page share one answer within a request.
  it('still resolves topic/locale via its own guest fallback even when the page credential is null', async () => {
    mockGetServerSession.mockResolvedValue(null)
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/auth/guest')) return jsonResponse({ access_token: 'guest-jwt' })
      if (url.includes('/topics')) return jsonResponse([{ id: 'topic-1' }])
      return jsonResponse({ available: [], resolved: 'en' })
    })
    const ctx = await resolveSsrContext()
    expect(ctx.credential).toBeNull()
    expect(ctx.topicId).toBe('topic-1')
  })

  it('degrades topic/locale to their null/"en" defaults when even the guest-fallback credential cannot be obtained', async () => {
    mockGetServerSession.mockResolvedValue(null)
    fetchMock.mockImplementation((url: string) =>
      url.includes('/auth/guest') ? jsonResponse({}, false) : jsonResponse([]),
    )
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBeNull()
    expect(ctx.locale).toBe('en')
  })

  // allowGuestCredential: true — only used by the unpaywalled home page (app/page.tsx).
  it('issues a one-time guest token when allowGuestCredential is true and there is no session', async () => {
    mockGetServerSession.mockResolvedValue(null)
    fetchMock.mockImplementation((url: string) =>
      url.includes('/auth/guest') ? jsonResponse({ access_token: 'guest-jwt' }) : jsonResponse([]),
    )
    const ctx = await resolveSsrContext({ allowGuestCredential: true })
    expect(ctx.credential).toBe('guest-jwt')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/auth/guest'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('still prefers a real session over a guest token when allowGuestCredential is true and a session exists', async () => {
    mockGetServerSession.mockResolvedValue({ accessToken: 'session-jwt' })
    fetchMock.mockResolvedValue(jsonResponse([]))
    const ctx = await resolveSsrContext({ allowGuestCredential: true })
    expect(ctx.credential).toBe('session-jwt')
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/auth/guest'), expect.anything())
  })

  it('degrades to a null credential when allowGuestCredential is true but guest-token issuance fails', async () => {
    mockGetServerSession.mockResolvedValue(null)
    fetchMock.mockImplementation((url: string) =>
      url.includes('/auth/guest') ? jsonResponse({}, false) : jsonResponse([]),
    )
    const ctx = await resolveSsrContext({ allowGuestCredential: true })
    expect(ctx.credential).toBeNull()
  })
})

describe('guest-token caching (root-cause-1 follow-up — reused across different requests/visitors)', () => {
  beforeEach(() => {
    mockGetServerSession.mockResolvedValue(null)
  })

  // Note: within a *single* resolveSsrContext() call, React's cache() would normally dedupe its
  // own direct resolveCredential() call against resolveVisitorTopicAndLocale()'s internal one —
  // but cache() isn't request-scoped outside a real Next.js render, so a bare Vitest call can't
  // observe that specific dedup the same way production does (harmless in production: cache()
  // only affects call *count* for a request that was always going to need a token either way).
  // What these tests verify instead — the property that actually matters for root cause 1 across
  // *different* visitors' renders — is the module-level cache itself: once warm, it doesn't grow.
  it('reuses a cached guest token across separate resolveSsrContext() calls instead of re-issuing one indefinitely', async () => {
    let guestTokenCalls = 0
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/auth/guest')) {
        guestTokenCalls += 1
        return jsonResponse({ access_token: 'guest-jwt', expires_in: 3600 })
      }
      return jsonResponse([])
    })

    await resolveSsrContext({ allowGuestCredential: true })
    const callsOnceWarm = guestTokenCalls
    const second = await resolveSsrContext({ allowGuestCredential: true })

    expect(second.credential).toBe('guest-jwt')
    expect(guestTokenCalls).toBe(callsOnceWarm)
  })

  it('issues a fresh token once the cached one is within its refresh margin of expiring', async () => {
    let issuedCount = 0
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/auth/guest')) {
        issuedCount += 1
        // expires_in: 30s — already inside the 60s refresh margin, so it's never treated as fresh.
        return jsonResponse({ access_token: `guest-jwt-${issuedCount}`, expires_in: 30 })
      }
      return jsonResponse([])
    })

    await resolveSsrContext({ allowGuestCredential: true })
    const countAfterFirst = issuedCount
    const second = await resolveSsrContext({ allowGuestCredential: true })

    // A second, separate call must issue at least one more token (never treats the near-expiry
    // cached one as still good) — proving the refresh-margin check itself works, independent of
    // exactly how many internal calls the first render happened to make in this test harness, and
    // independent of exactly which of resolveSsrContext's own internal concurrent calls "won"
    // and supplied its returned credential.
    expect(issuedCount).toBeGreaterThan(countAfterFirst)
    expect(second.credential).toMatch(/^guest-jwt-\d+$/)
  })

  it('does not cache a failed guest-token issuance — the next call retries', async () => {
    let attempts = 0
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/auth/guest')) {
        attempts += 1
        return attempts === 1 ? jsonResponse({}, false) : jsonResponse({ access_token: 'guest-jwt', expires_in: 3600 })
      }
      return jsonResponse([])
    })

    const first = await resolveSsrContext({ allowGuestCredential: true })
    const second = await resolveSsrContext({ allowGuestCredential: true })

    expect(first.credential).toBeNull()
    expect(second.credential).toBe('guest-jwt')
    expect(attempts).toBe(2)
  })
})

describe('resolveSsrContext — topic resolution', () => {
  beforeEach(() => {
    mockGetServerSession.mockResolvedValue({ accessToken: 'session-jwt' })
  })

  // Mirrors topic-provider.tsx's loadTopics(): no stored preference → first topic, not "no
  // filter" — a first-time visitor (no cookie yet) still gets a real, seeded default topic's
  // content server-side, same as their first client-side render would resolve to.
  it('falls back to the first topic when the cookie is absent', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    fetchMock.mockResolvedValue(jsonResponse([{ id: 'topic-1' }, { id: 'topic-2' }]))
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBe('topic-1')
  })

  // Root-cause-1 follow-up: a present cookie is trusted directly — no GET /topics round trip at
  // all — rather than validated first. This is what actually collapses the SSR fetch chain for
  // returning visitors.
  it('trusts a present cookie directly, without calling GET /topics', async () => {
    mockCookiesGet.mockImplementation((name: string) =>
      name === 'selectedTopicId' ? { value: 'topic-2' } : undefined,
    )
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBe('topic-2')
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/topics'), expect.anything())
  })

  // A cookie naming a deleted/deactivated topic (spec Edge Cases) is trusted anyway for this one
  // render — no longer validated/corrected server-side. The actual data fetch for that topic_id
  // just comes back empty, same as any other "no results" case; topic-provider.tsx's own
  // client-side loadTopics() validation (unchanged) corrects the cookie on its next run, so this
  // self-heals within one visit rather than paying a GET /topics round trip on every render.
  it('trusts a stale/deleted-topic cookie too, rather than validating it', async () => {
    mockCookiesGet.mockImplementation((name: string) =>
      name === 'selectedTopicId' ? { value: 'stale-topic' } : undefined,
    )
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBe('stale-topic')
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/topics'), expect.anything())
  })

  it('resolves null when there are no topics at all', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    fetchMock.mockResolvedValue(jsonResponse([]))
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBeNull()
  })

  it('falls back to null when GET /topics fails (no-cookie path — GET /topics is unavoidable here)', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    fetchMock.mockImplementation((url: string) =>
      url.includes('/topics') ? jsonResponse({}, false) : jsonResponse({}),
    )
    const ctx = await resolveSsrContext()
    expect(ctx.topicId).toBeNull()
  })
})

describe('resolveSsrContext — locale resolution', () => {
  beforeEach(() => {
    mockGetServerSession.mockResolvedValue({ accessToken: 'session-jwt' })
  })

  it('uses a supported locale cookie directly, without calling GET /languages', async () => {
    mockCookiesGet.mockImplementation((name: string) => (name === 'locale' ? { value: 'zh-TW' } : undefined))
    const ctx = await resolveSsrContext()
    expect(ctx.locale).toBe('zh-TW')
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining('/languages'), expect.anything())
  })

  it('geo-IP resolves via GET /languages, forwarding X-Forwarded-For, when the cookie is absent', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    mockHeadersGet.mockImplementation((name: string) => (name === 'x-forwarded-for' ? '203.0.113.1' : null))
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/languages')) {
        expect((init?.headers as Record<string, string>)?.['X-Forwarded-For']).toBe('203.0.113.1')
        return jsonResponse({ available: [], resolved: 'zh-TW' })
      }
      return jsonResponse([])
    })
    const ctx = await resolveSsrContext()
    expect(ctx.locale).toBe('zh-TW')
  })

  it('geo-IP resolves via GET /languages when the cookie value is unsupported', async () => {
    mockCookiesGet.mockImplementation((name: string) => (name === 'locale' ? { value: 'fr' } : undefined))
    fetchMock.mockImplementation((url: string) =>
      url.includes('/languages') ? jsonResponse({ available: [], resolved: 'en' }) : jsonResponse([]),
    )
    const ctx = await resolveSsrContext()
    expect(ctx.locale).toBe('en')
  })

  it('falls back to "en" when GET /languages fails', async () => {
    mockCookiesGet.mockReturnValue(undefined)
    fetchMock.mockImplementation((url: string) =>
      url.includes('/languages') ? jsonResponse({}, false) : jsonResponse([]),
    )
    const ctx = await resolveSsrContext()
    expect(ctx.locale).toBe('en')
  })
})

describe('fetchXSSR helpers — null-credential and failure fallback (FR-007)', () => {
  const noCredential: SsrContext = { credential: null, topicId: 'topic-1', locale: 'en' }
  const withCredential: SsrContext = { credential: 'tok', topicId: 'topic-1', locale: 'en' }

  it('fetchArticlesListSSR returns null without fetching when there is no credential', async () => {
    const result = await fetchArticlesListSSR(noCredential, new URLSearchParams())
    expect(result).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetchArticlesListSSR returns parsed data and the X-Cache status on success, including the context topic_id', async () => {
    fetchMock.mockImplementation((url: string) => {
      expect(url).toContain('topic_id=topic-1')
      return jsonResponse({ items: [{ id: 'a1' }], total: 1 }, true, 'HIT')
    })
    const result = await fetchArticlesListSSR(withCredential, new URLSearchParams())
    expect(result).toEqual({ value: { items: [{ id: 'a1' }], total: 1 }, cacheStatus: 'HIT' })
  })

  it('fetchArticlesListSSR returns null when the backend call throws', async () => {
    fetchMock.mockImplementation(() => { throw new Error('down') })
    const result = await fetchArticlesListSSR(withCredential, new URLSearchParams())
    expect(result).toBeNull()
  })

  it('fetchGraphSSR returns null when there is no resolved topic', async () => {
    const result = await fetchGraphSSR({ ...withCredential, topicId: null })
    expect(result).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetchGraphSSR returns null on a non-2xx response', async () => {
    fetchMock.mockResolvedValue(jsonResponse({}, false))
    const result = await fetchGraphSSR(withCredential)
    expect(result).toBeNull()
  })

  it('fetchTagGroupsSSR works with no topic filter at all (topic_id omitted)', async () => {
    fetchMock.mockImplementation((url: string) => {
      expect(url).not.toContain('topic_id')
      return jsonResponse([], true, 'MISS')
    })
    const result = await fetchTagGroupsSSR({ ...withCredential, topicId: null })
    expect(result).toEqual({ value: [], cacheStatus: 'MISS' })
  })

  it('fetchWeeklyReportSSR returns null when there is no resolved topic, matching WeeklyReportWidget parity', async () => {
    const result = await fetchWeeklyReportSSR({ ...withCredential, topicId: null })
    expect(result).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetchWeeklyReportSSR returns the report and X-Cache status on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'wr1' }, true, 'BYPASS'))
    const result = await fetchWeeklyReportSSR(withCredential)
    expect(result).toEqual({ value: { id: 'wr1' }, cacheStatus: 'BYPASS' })
  })
})
