import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const fixture = {
  id: 'abc',
  title: 'Test Article',
  source: 'rss',
  url: 'https://example.com',
  content: 'Article body text.',
  published_at: '2026-01-01T00:00:00Z',
  scraped_at: '2026-01-02T00:00:00Z',
}

vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: vi.fn().mockResolvedValue({
    id: 'abc',
    title: 'Test Article',
    source: 'rss',
    url: 'https://example.com',
    content: 'Article body text.',
    published_at: '2026-01-01T00:00:00Z',
    scraped_at: '2026-01-02T00:00:00Z',
    tags: [],
    tag_groups: [],
    pain_points: null,
    insights: null,
    innovations: null,
    model_used: 'test',
  }),
  recordArticleView: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ locale: 'en', t: (key: string) => key }),
  useTopic: () => ({ selectedTopicId: 'topic-1', topics: [], selectedTopic: null }),
  useGuestMode: () => ({ isGuestMode: false, enterGuestMode: vi.fn(), exitGuestMode: vi.fn() }),
  usePinnedArticle: () => ({
    pinnedArticles: [],
    togglePinnedArticle: vi.fn(),
    removePinnedArticle: vi.fn(),
    clearPinnedArticles: vi.fn(),
    isPinned: () => false,
  }),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: 'unauthenticated' }),
}))

describe('ArticleCard — share button', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders share button with aria-label', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByRole('button', { name: 'copy.shareArticle' })).toBeInTheDocument()
  })

  it('copies URL matching /articles/{id}?topic= format on share click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByRole('button', { name: 'copy.shareArticle' }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        expect.stringMatching(/\/articles\/abc\?topic=topic-1/)
      )
    })
  })

  it('shows success toast after successful clipboard copy', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    })
    const { toast } = await import('sonner')
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByRole('button', { name: 'copy.shareArticle' }))
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('copy.success')
    })
  })

  it('shows error toast when clipboard API throws', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
      configurable: true,
    })
    const { toast } = await import('sonner')
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByRole('button', { name: 'copy.shareArticle' }))
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('copy.failed')
    })
  })

  it('does not propagate click event to card when share button is clicked', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const onOpenChange = vi.fn()
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} open={false} onOpenChange={onOpenChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'copy.shareArticle' }))
    await waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(onOpenChange).not.toHaveBeenCalled()
  })
})

describe('ArticleCard — controlled open prop', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows dialog immediately when open=true without clicking card', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} open={true} onOpenChange={vi.fn()} />)
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('does not show dialog when open=false', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} open={false} onOpenChange={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('calls onOpenChange(true) when card is clicked in controlled mode', async () => {
    const onOpenChange = vi.fn()
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} open={false} onOpenChange={onOpenChange} />)
    fireEvent.click(screen.getByText('Test Article'))
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it('falls back to internal state when open prop is not provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })
})
