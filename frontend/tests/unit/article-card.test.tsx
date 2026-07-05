import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const fixture = {
  id: 'abc',
  title: 'Test Article',
  source: 'rss',
  url: 'https://example.com',
  content: 'Article body text.',
  published_at: '2026-01-01T00:00:00Z',
  scraped_at: '2026-01-02T00:00:00Z',
}

const detailFixture = {
  ...fixture,
  tags: [],
  tag_groups: [{ group_name: 'tech', display_name: 'Technology', color: '#6366f1', tags: ['AI', 'IoT'] }],
  pain_points: 'Key pain points here.',
  insights: 'Key insights here.',
  innovations: null,
  model_used: 'claude-test',
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
    tag_groups: [{ group_name: 'tech', display_name: 'Technology', color: '#6366f1', tags: ['AI', 'IoT'] }],
    pain_points: 'Key pain points here.',
    insights: 'Key insights here.',
    innovations: null,
    model_used: 'claude-test',
  }),
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

describe('ArticleCard', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders title and source', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByText('Test Article')).toBeInTheDocument()
    expect(screen.getByText('rss')).toBeInTheDocument()
  })

  it('renders formatted published date', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByText(/jan 1, 2026/i)).toBeInTheDocument()
  })

  it('clicking card opens dialog', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('dialog shows pain_points after loading', async () => {
    const { fetchArticleById } = await import('@/lib/api/articles')
    vi.mocked(fetchArticleById).mockResolvedValue(detailFixture as any)
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByText('Key pain points here.')).toBeInTheDocument()
    })
  })

  it('dialog shows insights after loading', async () => {
    const { fetchArticleById } = await import('@/lib/api/articles')
    vi.mocked(fetchArticleById).mockResolvedValue(detailFixture as any)
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    await act(async () => { fireEvent.click(screen.getByText('Test Article')) })
    await waitFor(() => {
      expect(screen.getByText('Key insights here.')).toBeInTheDocument()
    })
  })

  it('dialog shows tag badges', async () => {
    const { fetchArticleById } = await import('@/lib/api/articles')
    vi.mocked(fetchArticleById).mockResolvedValue(detailFixture as any)
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    fireEvent.click(screen.getByText('Test Article'))
    await waitFor(() => {
      expect(screen.getByText('AI')).toBeInTheDocument()
      expect(screen.getByText('IoT')).toBeInTheDocument()
    })
  })

  it('renders scraped_at date when provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    // scraped_at '2026-01-02T00:00:00Z' → Jan 2
    expect(screen.getByText(/jan 2/i)).toBeInTheDocument()
  })

  it('renders via_source badge when provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} via_source="arxiv" />)
    expect(screen.getByText(/arxiv/i)).toBeInTheDocument()
  })

  it('renders scraped_at date when provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.getByText(/jan 2/i)).toBeInTheDocument()
  })

  it('renders via_source badge when provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} via_source="arxiv" />)
    expect(screen.getByText(/arxiv/i)).toBeInTheDocument()
  })

  it('uses translated_title over original title when provided', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} translated_title="翻譯標題" />)
    expect(screen.getByText('翻譯標題')).toBeInTheDocument()
  })

  it('renders external link icon next to title', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    const link = screen.getAllByRole('link').find(l => l.getAttribute('href') === 'https://example.com')
    expect(link).toBeTruthy()
  })

  it('does not show dialog before card is clicked', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('sets tutorial target id on the pin button when isFirstTutorialTarget and has_vectors', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    const { container } = render(<ArticleCard {...fixture} has_vectors isFirstTutorialTarget />)
    expect(container.querySelector('#tutorial-target-chat-pin')).toBeInTheDocument()
  })

  it('does not set tutorial target id on the pin button when isFirstTutorialTarget is false', async () => {
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    const { container } = render(<ArticleCard {...fixture} has_vectors />)
    expect(container.querySelector('#tutorial-target-chat-pin')).not.toBeInTheDocument()
  })
})
