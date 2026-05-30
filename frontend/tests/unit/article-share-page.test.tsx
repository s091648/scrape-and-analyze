import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import React from 'react'

const mockUseParams = vi.fn()
const mockGetSearchParam = vi.fn(() => null)
const mockUseSession = vi.fn()
const mockFetchArticleById = vi.fn()

vi.mock('next/navigation', () => ({
  useParams: () => mockUseParams(),
  useSearchParams: () => ({ get: mockGetSearchParam }),
}))

vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}))

vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: (...args: unknown[]) => mockFetchArticleById(...args),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ locale: 'en', t: (key: string) => key }),
}))

vi.mock('@/components/features/articles/article-card', () => ({
  ArticleCard: ({ title }: { title: string }) => (
    <div data-testid="article-card">{title}</div>
  ),
  ArticleCardSkeleton: () => <div data-testid="article-skeleton">Loading...</div>,
}))

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))

const articleFixture = {
  id: 'art-001',
  title: 'Digital Twin Innovation',
  source: 'rss',
  content: 'Digital twins are revolutionizing manufacturing.',
  published_at: '2026-01-15T10:00:00Z',
  scraped_at: '2026-01-16T00:00:00Z',
  url: 'https://example.com/digital-twins',
  tags: [],
  tag_groups: [],
  pain_points: null,
  insights: null,
  innovations: null,
  model_used: 'test',
}

describe('ArticleSharePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mockUseParams.mockReturnValue({ articleId: 'art-001' })
    mockGetSearchParam.mockReturnValue(null)
    mockUseSession.mockReturnValue({ status: 'unauthenticated' })
  })

  it('shows skeleton while article is loading', async () => {
    mockFetchArticleById.mockReturnValue(new Promise(() => {}))
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    expect(screen.getByTestId('article-skeleton')).toBeInTheDocument()
  })

  it('renders article card after successful fetch', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByTestId('article-card')).toBeInTheDocument()
      expect(screen.getByText('Digital Twin Innovation')).toBeInTheDocument()
    })
  })

  it('shows 404 message when article fetch fails', async () => {
    mockFetchArticleById.mockRejectedValue(new Error('Not found'))
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByText('Article not found')).toBeInTheDocument()
    })
  })

  it('shows "Back to articles" link on 404', async () => {
    mockFetchArticleById.mockRejectedValue(new Error('Not found'))
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByText('Back to articles')).toBeInTheDocument()
    })
  })

  it('shows openInApp link when authenticated', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    mockUseSession.mockReturnValue({ status: 'authenticated' })
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByText('share.openInApp')).toBeInTheDocument()
    })
  })

  it('shows signInForMore link when unauthenticated and not guest', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    mockUseSession.mockReturnValue({ status: 'unauthenticated' })
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByText('share.signInForMore')).toBeInTheDocument()
    })
  })

  it('shows openInApp link when in guest mode', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    mockUseSession.mockReturnValue({ status: 'unauthenticated' })
    sessionStorage.setItem('guest_mode', 'true')
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(screen.getByText('share.openInApp')).toBeInTheDocument()
    })
  })

  it('calls fetchArticleById with the correct articleId and locale', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      expect(mockFetchArticleById).toHaveBeenCalledWith('art-001', 'en')
    })
  })

  it('openInApp link points to /?article= when no topic param', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    mockUseSession.mockReturnValue({ status: 'authenticated' })
    mockGetSearchParam.mockReturnValue(null)
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      const link = screen.getByText('share.openInApp').closest('a')
      expect(link?.getAttribute('href')).toMatch(/article=art-001/)
    })
  })

  it('openInApp link includes topic param when topic is in URL', async () => {
    mockFetchArticleById.mockResolvedValue(articleFixture)
    mockUseSession.mockReturnValue({ status: 'authenticated' })
    mockGetSearchParam.mockReturnValue('topic-001')
    const { default: ArticleSharePage } = await import('@/app/articles/[articleId]/page')
    render(<ArticleSharePage />)
    await waitFor(() => {
      const link = screen.getByText('share.openInApp').closest('a')
      expect(link?.getAttribute('href')).toMatch(/topic=topic-001/)
      expect(link?.getAttribute('href')).toMatch(/article=art-001/)
    })
  })
})
