import { useState } from 'react'
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

  it('renders a [N, M] grouped citation as one clickable marker per number', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const sources = [makeSource({ id: 'src-1', title: 'Paper One' }), makeSource({ id: 'src-2', title: 'Paper Two' })]
    render(<CitedContent text="A trend [1, 2] emerged." sources={sources} />)
    expect(screen.getByTitle('Paper One')).toBeInTheDocument()
    expect(screen.getByTitle('Paper Two')).toBeInTheDocument()
  })

  it('renders a grouped citation as literal text when any member is out of range', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="A trend [1, 5] emerged." sources={[makeSource()]} />)
    expect(screen.getByText(/\[1, 5\]/)).toBeInTheDocument()
  })

  it('renders extraContent between the parsed text and the source-chip row', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(
      <CitedContent
        text="See [1] for details."
        sources={[makeSource()]}
        extraContent={<p data-testid="extra">3 articles</p>}
      />
    )
    expect(screen.getByTestId('extra')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cited Paper/ })).toBeInTheDocument()
  })

  // ── Draggable source pills (2026-07-14, US10) ─────────────────────────────

  it('does not mark source pills as draggable by default', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} />)
    const chip = screen.getByRole('button', { name: /Cited Paper/ })
    expect(chip).not.toHaveAttribute('aria-roledescription')
  })

  it('marks source pills as draggable when draggableSources is set', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} draggableSources />)
    const chip = screen.getByRole('button', { name: /Cited Paper/ })
    expect(chip).toHaveAttribute('aria-roledescription', 'draggable')
  })

  // ── Reveal + highlight on inline-citation click (2026-07-14) ──────────────

  it('calls onRefClick with the 0-indexed source position when a [N] marker is clicked', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const onRefClick = vi.fn()
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} onRefClick={onRefClick} />)
    fireEvent.click(screen.getByTitle('Cited Paper'))
    expect(onRefClick).toHaveBeenCalledWith(0)
  })

  it('highlights the corresponding chip once a collapsed source list is expanded in response to onRefClick', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')

    function Wrapper() {
      const [expanded, setExpanded] = useState(false)
      return (
        <CitedContent
          text="See [1] for details."
          sources={[makeSource()]}
          showSourceList={expanded}
          onRefClick={() => setExpanded(true)}
        />
      )
    }

    render(<Wrapper />)
    expect(screen.queryByRole('button', { name: /Cited Paper/ })).not.toBeInTheDocument()

    fireEvent.click(screen.getByTitle('Cited Paper'))

    const chip = await screen.findByRole('button', { name: /Cited Paper/ })
    expect(chip.className).toContain('ring-2')
  })
})
