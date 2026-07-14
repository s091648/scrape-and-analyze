import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import type { ConversationTurn } from '@/components/features/chat/types'

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn()

const mockFetchArticleById = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: (...args: any[]) => mockFetchArticleById(...args),
}))

vi.mock('@/components/features/articles/article-detail-dialog', () => ({
  ArticleDetailDialog: vi.fn(() => null),
}))

const zhTW: Record<string, string> = {
  'rag.thinking': '思考中…',
  'rag.thinkingToggle': '思考過程',
  'rag.rateLimitError': '已達每日問答上限',
  'rag.serviceUnavailable': '問答服務暫時無法使用，請稍後再試',
  'rag.genericError': '發生錯誤，請稍後再試',
  'rag.previousTurn': '上一則問題',
  'rag.nextTurn': '下一則問題',
}

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k, locale: 'zh-TW' }),
}))

let turnCounter = 0
function makeTurn(content: string, opts: { thinking?: string; sources?: any[]; userContent?: string } = {}): ConversationTurn {
  turnCounter += 1
  const id = `a-${turnCounter}`
  return {
    userMessage: opts.userContent
      ? { id: `u-${turnCounter}`, role: 'user', content: opts.userContent, timestamp: new Date() }
      : undefined,
    assistantMessage: { id, role: 'assistant', content, thinking: opts.thinking, timestamp: new Date() },
    sources: opts.sources ?? [],
  }
}

const makeSource = (overrides = {}) => ({
  id: 'src-1',
  title: 'Test Article',
  url: 'https://example.com',
  public_article_id: null,
  ...overrides,
})

const noopPager = { onPrevTurn: vi.fn(), onNextTurn: vi.fn() }

describe('AnswerDisplay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    turnCounter = 0
    mockFetchArticleById.mockResolvedValue({
      title: 'Test Article',
      content: 'Content',
      url: 'https://example.com',
      source: 'rss',
      published_at: null,
      via_source: null,
      original_source: null,
    })
  })

  it('renders nothing when no turns and no loading/error', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const { container } = render(<AnswerDisplay turns={[]} currentIndex={0} {...noopPager} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows loading text when isLoading and no turns yet', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[]} currentIndex={0} isLoading {...noopPager} />)
    expect(screen.getByText('思考中…')).toBeInTheDocument()
  })

  it('shows assistant answer for the turn at currentIndex', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Hello world')]} currentIndex={0} {...noopPager} />)
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders markdown links as anchor tags with correct attributes', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        turns={[makeTurn('See [OpenAI](https://openai.com) for more.')]}
        currentIndex={0}
        {...noopPager}
      />
    )
    const link = screen.getByRole('link', { name: 'OpenAI' })
    expect(link).toHaveAttribute('href', 'https://openai.com')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('shows surrounding text around markdown links', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        turns={[makeTurn('See [Paper](https://arxiv.org/abs/123) here.')]}
        currentIndex={0}
        {...noopPager}
      />
    )
    expect(screen.getByText(/See/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Paper' })).toBeInTheDocument()
  })

  it('shows 429 rate limit error when no turns exist', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[]} currentIndex={0} error={new Error('HTTP 429')} {...noopPager} />)
    expect(screen.getByText('已達每日問答上限')).toBeInTheDocument()
  })

  it('shows 503 service unavailable error when no turns exist', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[]} currentIndex={0} error={new Error('HTTP 503')} {...noopPager} />)
    expect(screen.getByText('問答服務暫時無法使用，請稍後再試')).toBeInTheDocument()
  })

  it('shows generic error message for unknown errors when no turns exist', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[]} currentIndex={0} error={new Error('Network error')} {...noopPager} />)
    expect(screen.getByText('發生錯誤，請稍後再試')).toBeInTheDocument()
  })

  it('shows loading cursor when isLoading and currentIndex points at the last turn', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay turns={[makeTurn('Partial answer…')]} currentIndex={0} isLoading {...noopPager} />
    )
    expect(screen.getByText('Partial answer…')).toBeInTheDocument()
    const cursor = document.querySelector('.animate-pulse')
    expect(cursor).toBeInTheDocument()
  })

  it('does not show the loading cursor when isLoading but currentIndex points at an earlier turn', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        turns={[makeTurn('First answer'), makeTurn('Streaming in…')]}
        currentIndex={0}
        isLoading
        {...noopPager}
      />
    )
    expect(screen.getByText('First answer')).toBeInTheDocument()
    expect(document.querySelector('.animate-pulse')).not.toBeInTheDocument()
  })

  it('does not show error when a turn exists', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Got it')]} currentIndex={0} error={new Error('HTTP 429')} {...noopPager} />)
    expect(screen.queryByText('已達每日問答上限')).not.toBeInTheDocument()
    expect(screen.getByText('Got it')).toBeInTheDocument()
  })

  it('does not show loading text when isLoading but a turn already exists', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Streaming…')]} currentIndex={0} isLoading {...noopPager} />)
    expect(screen.queryByText('思考中…')).not.toBeInTheDocument()
  })

  it('renders multi-line content as separate paragraphs', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Line one\nLine two\nLine three')]} currentIndex={0} {...noopPager} />)
    expect(screen.getByText('Line one')).toBeInTheDocument()
    expect(screen.getByText('Line two')).toBeInTheDocument()
    expect(screen.getByText('Line three')).toBeInTheDocument()
  })

  it('renders bold markdown as <strong> element', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('This is **bold** text')]} currentIndex={0} {...noopPager} />)
    const bold = screen.getByText('bold')
    expect(bold.tagName).toBe('STRONG')
  })

  it('renders bullet list items', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('- First item\n- Second item')]} currentIndex={0} {...noopPager} />)
    expect(screen.getByText('First item')).toBeInTheDocument()
    expect(screen.getByText('Second item')).toBeInTheDocument()
    expect(document.querySelector('ul')).toBeInTheDocument()
  })

  it('renders external link source chip when source has no public_article_id', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'External Source', url: 'https://ext.com' })
    render(<AnswerDisplay turns={[makeTurn('Answer', { sources: [src] })]} currentIndex={0} {...noopPager} />)
    const link = screen.getByRole('link', { name: /External Source/ })
    expect(link).toHaveAttribute('href', 'https://ext.com')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders internal article button when source has public_article_id', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Internal Article', public_article_id: 'pub-123' })
    render(<AnswerDisplay turns={[makeTurn('Answer', { sources: [src] })]} currentIndex={0} {...noopPager} />)
    expect(screen.getByRole('button', { name: /Internal Article/ })).toBeInTheDocument()
  })

  it('uses url as display text for source chip when title is null', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: null, url: 'https://no-title.com' })
    render(<AnswerDisplay turns={[makeTurn('Answer', { sources: [src] })]} currentIndex={0} {...noopPager} />)
    expect(screen.getByRole('link', { name: /https:\/\/no-title\.com/ })).toBeInTheDocument()
  })

  it('calls fetchArticleById when internal source chip is clicked', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Clickable Article', public_article_id: 'pub-456' })
    render(<AnswerDisplay turns={[makeTurn('Answer', { sources: [src] })]} currentIndex={0} {...noopPager} />)
    fireEvent.click(screen.getByRole('button', { name: /Clickable Article/ }))
    await waitFor(() => {
      expect(mockFetchArticleById).toHaveBeenCalledWith('pub-456', 'zh-TW')
    })
  })

  it('renders [N] citation button when sources are provided', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Cited Paper' })
    render(<AnswerDisplay turns={[makeTurn('See [1] for details', { sources: [src] })]} currentIndex={0} {...noopPager} />)
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
  })

  it('does not render source chips when sources array is empty', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Answer', { sources: [] })]} currentIndex={0} {...noopPager} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('shows thinking toggle button when the turn has thinking content', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Answer', { thinking: 'Some reasoning...' })]} currentIndex={0} {...noopPager} />)
    expect(screen.getByRole('button', { name: /思考過程/ })).toBeInTheDocument()
  })

  it('hides thinking content by default (collapsed)', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Answer', { thinking: 'Hidden reasoning' })]} currentIndex={0} {...noopPager} />)
    expect(screen.queryByText('Hidden reasoning')).not.toBeInTheDocument()
  })

  it('shows thinking content when toggle is clicked', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Answer', { thinking: 'Visible reasoning' })]} currentIndex={0} {...noopPager} />)
    fireEvent.click(screen.getByRole('button', { name: /思考過程/ }))
    expect(screen.getByText('Visible reasoning')).toBeInTheDocument()
  })

  it('collapses thinking content when toggle clicked twice', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Answer', { thinking: 'Some reasoning' })]} currentIndex={0} {...noopPager} />)
    const toggle = screen.getByRole('button', { name: /思考過程/ })
    fireEvent.click(toggle)
    expect(screen.getByText('Some reasoning')).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.queryByText('Some reasoning')).not.toBeInTheDocument()
  })

  it('does not show thinking toggle when thinking is absent', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Normal answer')]} currentIndex={0} {...noopPager} />)
    expect(screen.queryByRole('button', { name: /思考過程/ })).not.toBeInTheDocument()
  })

  // ── Turn pager (2026-07-14) ────────────────────────────────────────────

  it('shows the paired user question above the answer', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('42', { userContent: 'What is the answer?' })]} currentIndex={0} {...noopPager} />)
    expect(screen.getByText('What is the answer?')).toBeInTheDocument()
  })

  it('does not render the pager when there is only one turn', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay turns={[makeTurn('Only answer')]} currentIndex={0} {...noopPager} />)
    expect(screen.queryByLabelText('上一則問題')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('下一則問題')).not.toBeInTheDocument()
  })

  it('renders the pager with position when multiple turns exist', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay turns={[makeTurn('First'), makeTurn('Second')]} currentIndex={1} {...noopPager} />
    )
    expect(screen.getByText('2 / 2')).toBeInTheDocument()
  })

  it('disables the previous button on the first turn and the next button on the last turn', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const { rerender } = render(
      <AnswerDisplay turns={[makeTurn('First'), makeTurn('Second')]} currentIndex={0} {...noopPager} />
    )
    expect(screen.getByLabelText('上一則問題')).toBeDisabled()
    expect(screen.getByLabelText('下一則問題')).not.toBeDisabled()

    rerender(<AnswerDisplay turns={[makeTurn('First'), makeTurn('Second')]} currentIndex={1} {...noopPager} />)
    expect(screen.getByLabelText('下一則問題')).toBeDisabled()
  })

  it('calls onPrevTurn / onNextTurn when the pager buttons are clicked', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const onPrevTurn = vi.fn()
    const onNextTurn = vi.fn()
    render(
      <AnswerDisplay
        turns={[makeTurn('First'), makeTurn('Second')]}
        currentIndex={1}
        onPrevTurn={onPrevTurn}
        onNextTurn={onNextTurn}
      />
    )
    fireEvent.click(screen.getByLabelText('上一則問題'))
    expect(onPrevTurn).toHaveBeenCalled()
  })

  it('hides the pager entirely while loading, even with multiple turns', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay turns={[makeTurn('First'), makeTurn('Second')]} currentIndex={1} isLoading {...noopPager} />
    )
    expect(screen.queryByLabelText('上一則問題')).not.toBeInTheDocument()
  })
})
