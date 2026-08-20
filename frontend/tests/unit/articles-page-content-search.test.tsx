import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import ArticlesPageContent from '@/app/articles/articles-page-content'

const { mockFetchArticles, mockSearchArticles } = vi.hoisted(() => ({
  mockFetchArticles: vi.fn(),
  mockSearchArticles: vi.fn(),
}))
vi.mock('@/lib/api/articles', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/articles')>()
  return { ...actual, fetchArticles: mockFetchArticles }
})
vi.mock('@/lib/api/search', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/search')>()
  return { ...actual, searchArticles: mockSearchArticles }
})

const { currentSearchParams } = vi.hoisted(() => ({ currentSearchParams: { current: new URLSearchParams() } }))
vi.mock('next/navigation', () => ({
  useSearchParams: () => currentSearchParams.current,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' }, status: 'authenticated' }),
}))

const { currentLocale } = vi.hoisted(() => ({ currentLocale: { current: 'en' } }))
vi.mock('@/lib/providers', () => ({
  useTopic: () => ({ selectedTopicId: 'topic-1' }),
  useI18n: () => ({ t: (k: string) => k, locale: currentLocale.current }),
  useGuestMode: () => ({ isGuestMode: false, enterGuestMode: vi.fn(), exitGuestMode: vi.fn() }),
  usePinnedArticle: () => ({
    pinnedArticles: [], togglePinnedArticle: vi.fn(), removePinnedArticle: vi.fn(),
    clearPinnedArticles: vi.fn(), isPinned: () => false,
  }),
}))

vi.mock('@/components/features/articles/use-metric-definitions', () => ({
  useMetricDefinitions: () => ({ definitions: [], isLoading: false }),
}))

function article(id: string, title: string, exact_match?: boolean) {
  return { id, title, source: 'rss', content: 'x', published_at: null, scraped_at: null, url: 'https://example.com', metrics: {}, view_count: 0, exact_match }
}

beforeEach(() => {
  vi.clearAllMocks()
  currentSearchParams.current = new URLSearchParams()
  currentLocale.current = 'en'
  Element.prototype.scrollIntoView = vi.fn()
})

describe('ArticlesPageContent — search (023-article-search)', () => {
  it('calls searchArticles instead of fetchArticles when q is present', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'machine learning' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'machine learning basics')], total: 1 })

    render(<ArticlesPageContent />)

    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    expect(mockFetchArticles).not.toHaveBeenCalled()
    expect(mockSearchArticles).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'machine learning', topic_id: 'topic-1' }),
      'en', 'test-token', expect.anything(),
    )
  })

  it('discards a stale (superseded) search response — only the later query result renders', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'first query' })

    // Mirrors real fetch/AbortController semantics (client.ts threads the caller's signal
    // into the underlying fetch, which rejects with AbortError on abort) — the mock must
    // behave the same way for this test to actually exercise the component's abort wiring,
    // not just its own promise bookkeeping.
    let firstSignal!: AbortSignal
    mockSearchArticles.mockImplementationOnce((_p, _l, _t, signal: AbortSignal) => {
      firstSignal = signal
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
      })
    })

    const { rerender } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    // Second query fires (and resolves) before the first one ever does — its rerender
    // triggers the effect's cleanup, which aborts firstSignal (and rejects the mocked
    // first call above, exactly as a real aborted fetch would).
    currentSearchParams.current = new URLSearchParams({ q: 'second query' })
    mockSearchArticles.mockResolvedValueOnce({ items: [article('a2', 'second query result')], total: 1 })
    rerender(<ArticlesPageContent />)

    // The matched query is highlighted via a <mark> + sibling text nodes (article-card.tsx),
    // so a plain string won't match the wrapping element — match on the innermost <span>'s
    // full textContent instead (same pattern as autocomplete-dropdown.test.tsx's getByTerm;
    // ancestor elements share the same textContent here since surrounding buttons/icons don't
    // contribute any of their own, so the match is narrowed to the SPAN tag specifically).
    await waitFor(() => {
      expect(
        screen.getByText((_content, element) => element?.tagName === 'SPAN' && element.textContent === 'Second Query Result')
      ).toBeInTheDocument()
    })
    expect(firstSignal.aborted).toBe(true)
    expect(screen.queryByText('First Query Result')).not.toBeInTheDocument()
  })

  it('reverts to fetchArticles when the search query is cleared', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'machine learning' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'search result')], total: 1 })

    const { rerender } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    currentSearchParams.current = new URLSearchParams()
    mockFetchArticles.mockResolvedValue({ items: [article('a2', 'normal listing')], total: 1 })
    rerender(<ArticlesPageContent />)

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Normal Listing')).toBeInTheDocument()
  })

  it('reverts to the normal listing after clearing a search that was already active on initial mount', async () => {
    // page.tsx's SSR fetch (buildArticlesQuery) never forwards `q` — it always seeds the plain
    // listing — so loading directly at a `?q=...` URL leaves the listing effect's very first
    // run short-circuited by its own `!searchQuery` guard, without ever reaching (and consuming)
    // the skipNextFetch guard below it. Regression test: skipNextFetch must not still be "banked"
    // by the time the search is later cleared, or the listing effect's revert fetch gets wrongly
    // skipped and stale search results are left on screen forever.
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'search result')], total: 1 })

    const { rerender } = render(
      <ArticlesPageContent initialArticles={[article('seed', 'seeded listing')]} initialTotal={1} />
    )
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    currentSearchParams.current = new URLSearchParams()
    mockFetchArticles.mockResolvedValue({ items: [article('a2', 'normal listing')], total: 1 })
    rerender(<ArticlesPageContent initialArticles={[article('seed', 'seeded listing')]} initialTotal={1} />)

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Normal Listing')).toBeInTheDocument()
  })

  // ── Exact-match-only filter ─────────────────────────────────────────────

  it('does not render the exact-match-only checkbox when there is no active search', async () => {
    mockFetchArticles.mockResolvedValue({ items: [article('a1', 'normal listing')], total: 1 })

    render(<ArticlesPageContent />)
    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('defaults to checked and requests exact_match_only=true from the server', async () => {
    // exact_match_only is enforced server-side (023-article-search follow-up regression:
    // a client-side per-page filter left total/pagination disagreeing with what was
    // actually shown once boost_exact_match sorted every exact match onto page 1) — the
    // mock's response simulates the server having already filtered, so only the exact
    // match is ever in `items` here.
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'literal hit', true)], total: 1 })

    render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    const checkbox = await screen.findByRole('checkbox')
    expect(checkbox).toHaveAttribute('data-state', 'checked')
    expect(mockSearchArticles).toHaveBeenCalledWith(
      expect.objectContaining({ q: 'cyberattacks', exact_match_only: true }),
      'en', 'test-token', expect.anything(),
    )
    expect(await screen.findByText('Literal Hit')).toBeInTheDocument()
  })

  it('re-fetches with exact_match_only=false and shows semantic neighbors once unchecked', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValueOnce({ items: [article('a1', 'literal hit', true)], total: 1 })

    render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    await screen.findByText('Literal Hit')

    mockSearchArticles.mockResolvedValueOnce({
      items: [article('a1', 'literal hit', true), article('a2', 'semantic neighbor', false)],
      total: 2,
    })
    fireEvent.click(screen.getByRole('checkbox'))

    expect(screen.getByRole('checkbox')).toHaveAttribute('data-state', 'unchecked')
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(2))
    expect(mockSearchArticles).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: 'cyberattacks', exact_match_only: false }),
      'en', 'test-token', expect.anything(),
    )
    expect(await screen.findByText('Semantic Neighbor')).toBeInTheDocument()
    expect(screen.getByText('Literal Hit')).toBeInTheDocument()
  })

  it('renders a help tooltip icon next to the exact-match-only checkbox when a search is active', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'literal hit', true)], total: 1 })

    const { container } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    await screen.findByRole('checkbox')

    expect(container.querySelector('.cursor-help')).toBeInTheDocument()
  })

  it('does not render the tooltip icon when there is no active search', async () => {
    mockFetchArticles.mockResolvedValue({ items: [article('a1', 'normal listing')], total: 1 })

    const { container } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))

    expect(container.querySelector('.cursor-help')).not.toBeInTheDocument()
  })

  // ── Filters/sort forwarded to search (023-article-search follow-up regression: these
  // were silently ignored while a search was active — see backend/services/search_service.py)

  it('forwards active filters to searchArticles alongside q', async () => {
    currentSearchParams.current = new URLSearchParams({
      q: 'cyberattacks', aggregator: 'techcrunch', tag: 'AI', published_after: '2026-01-01',
    })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'literal hit', true)], total: 1 })

    render(<ArticlesPageContent />)

    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    expect(mockSearchArticles).toHaveBeenCalledWith(
      expect.objectContaining({
        q: 'cyberattacks', aggregator: ['techcrunch'], tag: ['AI'], published_after: '2026-01-01',
      }),
      'en', 'test-token', expect.anything(),
    )
  })

  it('re-fetches when a filter changes while a search is already active', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'result')], total: 1 })

    const { rerender } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks', aggregator: 'techcrunch' })
    rerender(<ArticlesPageContent />)

    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(2))
    expect(mockSearchArticles).toHaveBeenLastCalledWith(
      expect.objectContaining({ aggregator: ['techcrunch'] }),
      'en', 'test-token', expect.anything(),
    )
  })

  it('does not send sort/order to searchArticles when the URL has no explicit sort param', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'result')], total: 1 })

    render(<ArticlesPageContent />)

    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    const callArgs = mockSearchArticles.mock.calls[0][0]
    expect(callArgs.sort).toBeUndefined()
    expect(callArgs.order).toBeUndefined()
  })

  it('sends sort/order to searchArticles once the URL has an explicit sort param', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks', sort: 'published_at', order: 'asc' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'result')], total: 1 })

    render(<ArticlesPageContent />)

    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    expect(mockSearchArticles).toHaveBeenCalledWith(
      expect.objectContaining({ sort: 'published_at', order: 'asc' }),
      'en', 'test-token', expect.anything(),
    )
  })

  it('reflects the server-filtered total in the page count instead of the raw items length', async () => {
    // Regression: totalPages was previously computed from the unfiltered `total` while
    // exact_match_only filtered `items` per-page client-side — a later page could render
    // zero cards while pagination still claimed more pages existed. `total` must now be
    // whatever exact_match_only-filtered value the server returns.
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({
      items: [article('a1', 'literal hit', true)],
      total: 1, // server already applied exact_match_only=true — total reflects just this
    })

    render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))
    await screen.findByText('Literal Hit')

    expect(screen.getByText('1')).toBeInTheDocument() // the count badge — not some unfiltered count
  })
})

describe('ArticlesPageContent — locale change clears an active search', () => {
  it('clears the search query (pushes q out of the URL) when locale changes', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'result')], total: 1 })

    const { rerender } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {})
    currentLocale.current = 'zh-TW'
    rerender(<ArticlesPageContent />)

    await waitFor(() => expect(pushStateSpy).toHaveBeenCalled())
    const pushedUrl = pushStateSpy.mock.calls[0][2] as string
    expect(pushedUrl).not.toContain('q=cyberattacks')
    pushStateSpy.mockRestore()
  })

  it('does not clear the search on the initial render (mount is not a locale "change")', async () => {
    currentSearchParams.current = new URLSearchParams({ q: 'cyberattacks' })
    mockSearchArticles.mockResolvedValue({ items: [article('a1', 'result')], total: 1 })

    const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {})
    render(<ArticlesPageContent />)
    await waitFor(() => expect(mockSearchArticles).toHaveBeenCalledTimes(1))

    expect(pushStateSpy).not.toHaveBeenCalled()
    pushStateSpy.mockRestore()
  })

  it('does not push a URL change when locale changes and there is no active search', async () => {
    currentSearchParams.current = new URLSearchParams()
    mockFetchArticles.mockResolvedValue({ items: [article('a1', 'listing')], total: 1 })

    const { rerender } = render(<ArticlesPageContent />)
    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))

    const pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {})
    currentLocale.current = 'zh-TW'
    mockFetchArticles.mockResolvedValue({ items: [article('a2', 'listing')], total: 1 })
    rerender(<ArticlesPageContent />)

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(2))
    expect(pushStateSpy).not.toHaveBeenCalled()
    pushStateSpy.mockRestore()
  })
})
