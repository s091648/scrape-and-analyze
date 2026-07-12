import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: 'unauthenticated' }),
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

const mockUseMetricDefinitions = vi.fn()
vi.mock('@/components/features/articles/use-metric-definitions', () => ({
  useMetricDefinitions: () => mockUseMetricDefinitions(),
}))

describe('ArticleCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseMetricDefinitions.mockReturnValue({})
  })

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

  // ── Generalized metrics badges (2026-07-12, US8) ─────────────────────────

  it('renders a badge for each enabled metric present on the article', async () => {
    mockUseMetricDefinitions.mockReturnValue({
      citation_count: { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: 'integer', unit: null },
    })
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} metrics={{ citation_count: 42 }} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('does not render a badge for a metric that is not currently enabled', async () => {
    mockUseMetricDefinitions.mockReturnValue({})
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} metrics={{ citation_count: 42 }} />)
    expect(screen.queryByText('42')).not.toBeInTheDocument()
  })

  it('renders a badge for every enabled metric when an article has more than one', async () => {
    mockUseMetricDefinitions.mockReturnValue({
      citation_count: { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: 'integer', unit: null },
      impact_factor: { metric_key: 'impact_factor', label_i18n_key: 'metrics.impact_factor', icon_name: null, format_hint: 'decimal', unit: null },
    })
    const { ArticleCard } = await import('@/components/features/articles/article-card')
    render(<ArticleCard {...fixture} metrics={{ citation_count: 42, impact_factor: 3.5 }} />)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('3.5')).toBeInTheDocument()
  })
})
