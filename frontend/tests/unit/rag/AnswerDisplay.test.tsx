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

const zhTW: Record<string, string> = {
  'rag.thinking': '思考中…',
  'rag.rateLimitError': '已達每日問答上限',
  'rag.serviceUnavailable': '問答服務暫時無法使用，請稍後再試',
  'rag.genericError': '發生錯誤，請稍後再試',
}

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k, locale: 'zh-TW' }),
}))

const makeMessage = (id: string, role: 'user' | 'assistant', content: string) => ({
  id,
  role,
  content,
  timestamp: new Date(),
})

const makeSource = (overrides = {}) => ({
  id: 'src-1',
  title: 'Test Article',
  url: 'https://example.com',
  public_article_id: null,
  ...overrides,
})

describe('AnswerDisplay', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it('renders nothing when no messages and no loading/error', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const { container } = render(<AnswerDisplay messages={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows loading text when isLoading and no assistant message', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay messages={[]} isLoading />)
    expect(screen.getByText('思考中…')).toBeInTheDocument()
  })

  it('shows assistant answer when messages include assistant reply', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay messages={[makeMessage('1', 'assistant', 'Hello world')]} />)
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders markdown links as anchor tags with correct attributes', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[
          makeMessage('1', 'assistant', 'See [OpenAI](https://openai.com) for more.'),
        ]}
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
        messages={[makeMessage('1', 'assistant', 'See [Paper](https://arxiv.org/abs/123) here.')]}
      />
    )
    expect(screen.getByText(/See/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Paper' })).toBeInTheDocument()
  })

  it('shows 429 rate limit error when no assistant message', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay messages={[]} error={new Error('HTTP 429')} />)
    expect(screen.getByText('已達每日問答上限')).toBeInTheDocument()
  })

  it('shows 503 service unavailable error when no assistant message', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay messages={[]} error={new Error('HTTP 503')} />)
    expect(screen.getByText('問答服務暫時無法使用，請稍後再試')).toBeInTheDocument()
  })

  it('shows generic error message for unknown errors when no assistant message', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(<AnswerDisplay messages={[]} error={new Error('Network error')} />)
    expect(screen.getByText('發生錯誤，請稍後再試')).toBeInTheDocument()
  })

  it('shows loading cursor when isLoading with existing assistant message', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Partial answer…')]}
        isLoading
      />
    )
    expect(screen.getByText('Partial answer…')).toBeInTheDocument()
    const cursor = document.querySelector('.animate-pulse')
    expect(cursor).toBeInTheDocument()
  })

  it('uses the last assistant message when multiple exist', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[
          makeMessage('1', 'assistant', 'First answer'),
          makeMessage('2', 'user', 'Follow-up question'),
          makeMessage('3', 'assistant', 'Latest answer'),
        ]}
      />
    )
    expect(screen.getByText('Latest answer')).toBeInTheDocument()
    expect(screen.queryByText('First answer')).not.toBeInTheDocument()
  })

  it('does not show error when an assistant message exists', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Got it')]}
        error={new Error('HTTP 429')}
      />
    )
    expect(screen.queryByText('已達每日問答上限')).not.toBeInTheDocument()
    expect(screen.getByText('Got it')).toBeInTheDocument()
  })

  it('does not show loading text when isLoading but assistant message already exists', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Streaming…')]}
        isLoading
      />
    )
    expect(screen.queryByText('思考中…')).not.toBeInTheDocument()
  })

  it('renders multi-line content as separate paragraphs', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Line one\nLine two\nLine three')]}
      />
    )
    expect(screen.getByText('Line one')).toBeInTheDocument()
    expect(screen.getByText('Line two')).toBeInTheDocument()
    expect(screen.getByText('Line three')).toBeInTheDocument()
  })

  it('renders bold markdown as <strong> element', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'This is **bold** text')]}
      />
    )
    const bold = screen.getByText('bold')
    expect(bold.tagName).toBe('STRONG')
  })

  it('renders bullet list items', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', '- First item\n- Second item')]}
      />
    )
    expect(screen.getByText('First item')).toBeInTheDocument()
    expect(screen.getByText('Second item')).toBeInTheDocument()
    expect(document.querySelector('ul')).toBeInTheDocument()
  })

  it('renders external link source chip when source has no public_article_id', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'External Source', url: 'https://ext.com' })
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Answer')]}
        sources={[src]}
      />
    )
    const link = screen.getByRole('link', { name: /External Source/ })
    expect(link).toHaveAttribute('href', 'https://ext.com')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders internal article button when source has public_article_id', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Internal Article', public_article_id: 'pub-123' })
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Answer')]}
        sources={[src]}
      />
    )
    expect(screen.getByRole('button', { name: /Internal Article/ })).toBeInTheDocument()
  })

  it('uses url as display text for source chip when title is null', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: null, url: 'https://no-title.com' })
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Answer')]}
        sources={[src]}
      />
    )
    expect(screen.getByRole('link', { name: /https:\/\/no-title\.com/ })).toBeInTheDocument()
  })

  it('calls fetchArticleById when internal source chip is clicked', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Clickable Article', public_article_id: 'pub-456' })
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Answer')]}
        sources={[src]}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /Clickable Article/ }))
    await waitFor(() => {
      expect(mockFetchArticleById).toHaveBeenCalledWith('pub-456', 'zh-TW')
    })
  })

  it('renders [N] citation button when sources are provided', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    const src = makeSource({ title: 'Cited Paper' })
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'See [1] for details')]}
        sources={[src]}
      />
    )
    // citation button renders the number
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
  })

  it('does not render source chips when sources array is empty', async () => {
    const { AnswerDisplay } = await import('@/components/features/chat/AnswerDisplay')
    render(
      <AnswerDisplay
        messages={[makeMessage('1', 'assistant', 'Answer')]}
        sources={[]}
      />
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
