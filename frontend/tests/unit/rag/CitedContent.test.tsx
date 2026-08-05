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

  // A model that invents a citation number beyond the real source count (e.g. mistaking one
  // pinned article's several paragraphs for several sources) has nothing valid to show for it —
  // the backend can't tell which real article "[2]" was supposed to mean, so it's dropped
  // silently rather than left in as broken-looking literal "[2]" text.
  it('silently drops an out-of-range [N] instead of showing broken literal text', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="See [2] for details." sources={[makeSource()]} />)
    expect(screen.queryByText(/\[2\]/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument()
    expect(screen.getByText(/See\s+for details\./)).toBeInTheDocument()
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

  // Regression for the real-world report: a pinned single article's several paragraphs get
  // mistaken for several sources, producing a group like "[1, 5]" where only 1 is real. The old
  // all-or-nothing behavior showed the whole group as broken literal text; it should instead
  // render a pill for the one real member and drop the invented one.
  it('renders only the valid member of a grouped citation, dropping invented ones', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(<CitedContent text="A trend [1, 5] emerged." sources={[makeSource()]} />)
    expect(screen.queryByText(/\[1, 5\]/)).not.toBeInTheDocument()
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '5' })).not.toBeInTheDocument()
  })

  // Regression for a real pinned-article report: only article 1 is a real source, but the model
  // scattered invented numbers ([2,3], [3,6], [9], [4,5,8]) through the answer as if the
  // article's paragraphs were separate sources. The reply should read cleanly — only the real
  // "[1]" citations survive as pills, everything else vanishes without a trace.
  it('cleans up a reply with many invented citation numbers down to just the one real source', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const text =
      'This platform solves operational challenges [2, 3]. ' +
      'It uses AWS IoT Core for edge-to-cloud connectivity [3, 6]. ' +
      'This reduced downtime [1, 3]. ' +
      'It also improves R&D feedback [9]. ' +
      'It lays groundwork for AI features [4, 5, 8].'
    render(<CitedContent text={text} sources={[makeSource({ number: 1 })]} />)
    for (const invented of ['2, 3', '3, 6', '9', '4, 5, 8']) {
      expect(screen.queryByText(new RegExp(`\\[${invented}\\]`))).not.toBeInTheDocument()
    }
    // The one real citation ("[1, 3]", containing the real number 1) still renders its pill.
    expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '3' })).not.toBeInTheDocument()
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

  // Regression: a source with no public_article_id has nothing valid to pin — `src.id` is
  // chatbot-plugin's own internal vector-DB row id, meaningless in the main app's article
  // space. Dragging it used to pin that internal id anyway, silently producing a pin that could
  // never resolve to any RAG content (the chat would just report "no article content provided").
  it('does not mark a source pill as draggable when it has no public_article_id, even with draggableSources set', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    render(
      <CitedContent
        text="See [1] for details."
        sources={[makeSource({ public_article_id: null })]}
        draggableSources
      />
    )
    const chip = screen.getByText('Cited Paper').closest('a, button')!
    expect(chip).not.toHaveAttribute('aria-roledescription')
  })

  // ── Reveal + highlight on inline-citation click (2026-07-14) ──────────────

  it('calls onRefClick with the 0-indexed source position when a [N] marker is clicked', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const onRefClick = vi.fn()
    render(<CitedContent text="See [1] for details." sources={[makeSource()]} onRefClick={onRefClick} />)
    fireEvent.click(screen.getByTitle('Cited Paper'))
    expect(onRefClick).toHaveBeenCalledWith(0)
  })

  // ── Non-contiguous citation numbering (chat's sources are narrowed to only the cited
  // articles server-side, so array position can diverge from the literal [N] marker) ──────────

  it('resolves a [N] marker by source.number, not array position, when sources are non-contiguous', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    // Only articles 2 and 4 were cited (1 and 3 were skipped) — sources[] is compacted to
    // [article2, article4], but the text still says "[2]" and "[4]" literally.
    const sources = [
      makeSource({ id: 'src-2', title: 'Article Two', number: 2 }),
      makeSource({ id: 'src-4', title: 'Article Four', number: 4 }),
    ]
    render(<CitedContent text="See [2] and [4] for details." sources={sources} />)
    // A naive sources[N-1] lookup would map "[2]" to sources[1] (Article Four) — wrong.
    const chip2 = screen.getByTitle('Article Two')
    const chip4 = screen.getByTitle('Article Four')
    expect(chip2).toBeInTheDocument()
    expect(chip4).toBeInTheDocument()
  })

  it('calls onRefClick with the correct array index (not marker-1) for non-contiguous numbered sources', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const onRefClick = vi.fn()
    const sources = [
      makeSource({ id: 'src-2', title: 'Article Two', number: 2 }),
      makeSource({ id: 'src-4', title: 'Article Four', number: 4 }),
    ]
    render(<CitedContent text="See [4] for details." sources={sources} onRefClick={onRefClick} />)
    fireEvent.click(screen.getByTitle('Article Four'))
    // "[4]" is sources[1] (Article Four), not sources[3] (out of bounds) or sources[0].
    expect(onRefClick).toHaveBeenCalledWith(1)
  })

  it('shows the original marker number, not array position, on the source chip', async () => {
    const { CitedContent } = await import('@/components/features/chat/cited-content')
    const sources = [
      makeSource({ id: 'src-2', title: 'Article Two', number: 2 }),
      makeSource({ id: 'src-4', title: 'Article Four', number: 4 }),
    ]
    render(<CitedContent text="See [2] and [4] for details." sources={sources} />)
    const chipRow = screen.getByTitle('Article Two').closest('button')!.parentElement!
    expect(chipRow.textContent).toContain('2')
    expect(chipRow.textContent).toContain('4')
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
