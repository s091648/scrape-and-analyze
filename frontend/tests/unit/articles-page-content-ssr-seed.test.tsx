import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import ArticlesPageContent from '@/app/articles/articles-page-content'

const { mockFetchArticles } = vi.hoisted(() => ({ mockFetchArticles: vi.fn() }))
vi.mock('@/lib/api/articles', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/articles')>()
  return { ...actual, fetchArticles: mockFetchArticles }
})

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' }, status: 'authenticated' }),
}))

// Mutable so a test can change the resolved topic between renders, to simulate an effect
// dependency (selectedTopicId) actually changing after mount — without needing to also fake
// Next's router/searchParams round-trip just to prove the same underlying guard behavior.
const { currentTopicId } = vi.hoisted(() => ({ currentTopicId: { current: 'topic-1' } }))
vi.mock('@/lib/providers', () => ({
  useTopic: () => ({ selectedTopicId: currentTopicId.current }),
  useI18n: () => ({ t: (k: string) => k, locale: 'en' }),
  useGuestMode: () => ({ isGuestMode: false, enterGuestMode: vi.fn(), exitGuestMode: vi.fn() }),
  usePinnedArticle: () => ({
    pinnedArticles: [],
    togglePinnedArticle: vi.fn(),
    removePinnedArticle: vi.fn(),
    clearPinnedArticles: vi.fn(),
    isPinned: () => false,
  }),
}))

vi.mock('@/components/features/articles/use-metric-definitions', () => ({
  useMetricDefinitions: () => ({ definitions: [], isLoading: false }),
}))

const seededArticle = {
  id: 'seeded-1',
  // No hyphens/mixed casing — ArticleCard renders titles through toTitleCase()
  // (components/features/articles/source-utils.ts), which only capitalizes the first letter
  // of each space-separated word, so a plain all-lowercase multi-word title round-trips exactly.
  title: 'seeded article marker',
  source: 'rss',
  content: 'x',
  published_at: null,
  scraped_at: null,
  url: 'https://example.com',
  metrics: {},
  view_count: 0,
}

const clientFetchedArticle = {
  ...seededArticle,
  id: 'client-fetched-1',
  title: 'client fetched article marker',
}

beforeEach(() => {
  vi.clearAllMocks()
  currentTopicId.current = 'topic-1'
  mockFetchArticles.mockResolvedValue({ items: [clientFetchedArticle], total: 1 })
})

describe('ArticlesPageContent — SSR seed guard (021-ssr-public-pages FR-003/SC-004)', () => {
  it('does NOT call fetchArticles on mount when seeded with initialArticles', async () => {
    render(<ArticlesPageContent initialArticles={[seededArticle]} initialTotal={1} />)

    expect(await screen.findByText('Seeded Article Marker')).toBeInTheDocument()
    // Give any stray effect a tick to fire, then confirm it never did.
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchArticles).not.toHaveBeenCalled()
  })

  it('DOES call fetchArticles on mount when not seeded (undefined initialArticles)', async () => {
    render(<ArticlesPageContent />)

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Client Fetched Article Marker')).toBeInTheDocument()
  })

  it('still fetches normally once a real dependency (selectedTopicId) changes after a seeded mount', async () => {
    const { rerender } = render(<ArticlesPageContent initialArticles={[seededArticle]} initialTotal={1} />)
    await screen.findByText('Seeded Article Marker')
    expect(mockFetchArticles).not.toHaveBeenCalled()

    // Simulates the visitor switching topics — a real effect-dependency change, distinct from
    // the one-time seeded mount the guard is meant to skip.
    currentTopicId.current = 'topic-2'
    rerender(<ArticlesPageContent initialArticles={[seededArticle]} initialTotal={1} />)

    await waitFor(() => expect(mockFetchArticles).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Client Fetched Article Marker')).toBeInTheDocument()
  })

  it('treats an empty seeded array as real seeded data (still skips the mount fetch)', async () => {
    render(<ArticlesPageContent initialArticles={[]} initialTotal={0} />)
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchArticles).not.toHaveBeenCalled()
  })
})
