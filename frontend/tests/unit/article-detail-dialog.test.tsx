import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const mockUseI18n = vi.fn()
vi.mock('@/lib/providers', () => ({
  useI18n: () => mockUseI18n(),
}))

vi.mock('@/components/features/articles/article-card-skeleton', () => ({
  ArticleDetailSkeleton: () => <div data-testid="detail-skeleton" />,
}))

vi.mock('@/components/features/articles/source-utils', () => ({
  deriveDisplaySource: (_url: string, source: string) => source,
  formatViaSource: (v: string) => `via:${v}`,
}))

const mockUseMetricDefinitions = vi.fn()
vi.mock('@/components/features/articles/use-metric-definitions', () => ({
  useMetricDefinitions: () => mockUseMetricDefinitions(),
}))

const baseProps = {
  open: true,
  onOpenChange: vi.fn(),
  title: 'Test Article Title',
  source: 'rss',
  url: 'https://example.com/article',
  via_source: null as string | null | undefined,
  original_source: null as string | null | undefined,
  published_at: '2026-01-15T00:00:00Z' as string | null,
  content: 'Article content here.',
  detail: null as any,
  loading: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUseI18n.mockReturnValue({ t: (k: string) => k, locale: 'en' })
  mockUseMetricDefinitions.mockReturnValue({})
})

describe('ArticleDetailDialog', () => {
  it('renders article title as a link', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} />)
    const link = screen.getByRole('link', { name: /Test Article Title/i })
    expect(link).toHaveAttribute('href', 'https://example.com/article')
  })

  it('shows article content', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} />)
    expect(screen.getByText('Article content here.')).toBeInTheDocument()
  })

  it('shows loading skeleton when loading=true', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} loading={true} />)
    expect(screen.getByTestId('detail-skeleton')).toBeInTheDocument()
  })

  it('does not show skeleton when loading=false', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} />)
    expect(screen.queryByTestId('detail-skeleton')).not.toBeInTheDocument()
  })

  it('shows formatted published date', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} />)
    expect(screen.getByText(/Jan 15, 2026/i)).toBeInTheDocument()
  })

  it('does not show date when published_at is null', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} published_at={null} />)
    expect(screen.queryByText(/Jan/i)).not.toBeInTheDocument()
  })

  it('shows via_source badge when provided', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} via_source="arxiv" />)
    expect(screen.getByText('via:arxiv')).toBeInTheDocument()
  })

  it('does not show via_source badge when null', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} via_source={null} />)
    expect(screen.queryByText(/via:/)).not.toBeInTheDocument()
  })

  it('shows source display text', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} />)
    expect(screen.getByText('rss')).toBeInTheDocument()
  })

  it('shows a metric badge when the article has an enabled metric', async () => {
    mockUseMetricDefinitions.mockReturnValue({
      citation_count: { metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count', icon_name: 'quote', format_hint: 'integer', unit: null },
    })
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = { ...baseProps.detail, metrics: { citation_count: 42 } }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByText(/42 metrics\.citation_count/)).toBeInTheDocument()
  })

  it('does not show a metric badge for a metric that is not currently enabled', async () => {
    mockUseMetricDefinitions.mockReturnValue({})
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = { ...baseProps.detail, metrics: { citation_count: 42 } }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.queryByText(/42/)).not.toBeInTheDocument()
  })

  it('does not render dialog content when open=false', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} open={false} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('uses translated_title over title when detail provides one', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'Original Title', content: 'C', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: 'Translated Title', translated_content: null,
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByText('Translated Title')).toBeInTheDocument()
  })

  it('uses translated_content over content when detail provides one', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'T', content: 'original', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: null, translated_content: 'translated content',
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByText('translated content')).toBeInTheDocument()
  })

  it('shows translation disclaimer when locale is not en and translated content exists', async () => {
    mockUseI18n.mockReturnValue({ t: (k: string) => k, locale: 'zh-TW' })
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'T', content: 'C', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: 'TW Title', translated_content: 'TW Content',
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByText('analysis.translationDisclaimer')).toBeInTheDocument()
  })

  it('does not show translation disclaimer when locale is en', async () => {
    mockUseI18n.mockReturnValue({ t: (k: string) => k, locale: 'en' })
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'T', content: 'C', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: 'TW Title', translated_content: 'TW Content',
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.queryByText('analysis.translationDisclaimer')).not.toBeInTheDocument()
  })
})

describe('ArticleDetailDialog — no analysis state', () => {
  it('shows "No analysis available" when detail exists but has no model_used', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'T', content: 'C', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: null, translated_content: null,
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByText('No analysis available yet.')).toBeInTheDocument()
  })

  it('shows disabled "Create Analysis" button when no model_used', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = {
      title: 'T', content: 'C', url: 'U', source: 's',
      published_at: null, model_used: null, tag_groups: [],
      pain_points: null, insights: null, innovations: null,
      via_source: null, original_source: null,
      translated_title: null, translated_content: null,
    }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.getByRole('button', { name: 'Create Analysis' })).toBeDisabled()
  })
})

describe('ArticleDetailDialog — analysis section', () => {
  const analysisDetail = {
    title: 'T', content: 'C', url: 'U', source: 's',
    published_at: null, model_used: 'gemini-flash',
    tag_groups: [{ group_name: 'tech', display_name: 'Technology', color: '#6366f1', tags: ['AI', 'ML'] }],
    pain_points: 'Key pain points.',
    insights: 'Key insights.',
    innovations: 'Novel innovations.',
    via_source: null, original_source: null,
    translated_title: null, translated_content: null,
  }

  it('shows pain_points when detail has model_used', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.getByText('Key pain points.')).toBeInTheDocument()
  })

  it('shows insights when detail has model_used', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.getByText('Key insights.')).toBeInTheDocument()
  })

  it('shows innovations when detail has model_used', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.getByText('Novel innovations.')).toBeInTheDocument()
  })

  it('renders tag badges when tag_groups provided', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.getByText('AI')).toBeInTheDocument()
    expect(screen.getByText('ML')).toBeInTheDocument()
  })

  it('shows tag group display_name', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.getByText('Technology')).toBeInTheDocument()
  })

  it('does not show "No analysis" section when model_used is set', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    render(<ArticleDetailDialog {...baseProps} detail={analysisDetail as any} />)
    expect(screen.queryByText('No analysis available yet.')).not.toBeInTheDocument()
  })

  it('does not render pain_points section when null', async () => {
    const { ArticleDetailDialog } = await import('@/components/features/articles/article-detail-dialog')
    const detail = { ...analysisDetail, pain_points: null }
    render(<ArticleDetailDialog {...baseProps} detail={detail as any} />)
    expect(screen.queryByText('analysis.painPoints')).not.toBeInTheDocument()
  })
})
