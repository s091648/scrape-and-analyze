import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn()

const mockFetchArticleById = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: (...args: any[]) => mockFetchArticleById(...args),
}))

vi.mock('@/components/features/articles/article-detail-dialog', () => ({
  ArticleDetailDialog: vi.fn(() => null),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => k, locale: 'en' }),
}))

const makeSource = (overrides = {}) => ({
  id: 'src-1',
  title: 'Cited Paper',
  url: 'https://example.com/paper',
  public_article_id: 'pub-1',
  ...overrides,
})

describe('CitedContent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchArticleById.mockResolvedValue({
      title: 'Cited Paper',
      content: 'Content',
      url: 'https://example.com/paper',
      source: 'rss',
      published_at: null,
      via_source: null,
      original_source: null,
    })
  })

  it('renders [N] as a clickable marker when N is within sources range', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} />)
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
  })

  it('renders an out-of-range [N] as literal text, not a clickable marker', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [2] for details." sources={[makeSource()]} />)
    expect(screen.getByText(/\[2\]/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument()
  })

  it('renders [N] as literal text when no sources are provided', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." />)
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument()
  })

  it('hides the source-chip row when showSourceList is false, but still linkifies inline citations', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} showSourceList={false} />)
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cited Paper/ })).not.toBeInTheDocument()
  })

  it('shows the source-chip row by default when sources are present', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} />)
    expect(screen.getByRole('button', { name: /Cited Paper/ })).toBeInTheDocument()
  })

  it('opens the article dialog when a source chip is clicked', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} />)
    fireEvent.click(screen.getByRole('button', { name: /Cited Paper/ }))
    await waitFor(() => {
      expect(mockFetchArticleById).toHaveBeenCalledWith('pub-1', 'en')
    })
  })
})
