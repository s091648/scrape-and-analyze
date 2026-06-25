import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// jsdom does not implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn()

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => k, locale: 'zh-TW' }),
}))

const mockFetchArticleById = vi.fn()
vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: (...args: any[]) => mockFetchArticleById(...args),
}))

vi.mock('@/components/features/articles/article-detail-dialog', () => ({
  ArticleDetailDialog: vi.fn(() => null),
}))

const makeMessage = (id: string, role: 'user' | 'assistant', content: string) => ({
  id,
  role,
  content,
  timestamp: new Date('2024-01-01T10:00:00'),
})

describe('FloatingChatbotPanel', () => {
  const defaultProps = {
    messages: [],
    messageSources: {},
    onSend: vi.fn(),
    isLoading: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchArticleById.mockResolvedValue({
      title: 'Test Article',
      content: 'Content',
      url: 'https://example.com',
      source: 'Test Source',
      published_at: null,
      via_source: null,
      original_source: null,
    })
  })

  // i18n mock returns the key itself, so aria-labels equal the translation key
  const openPanel = () => fireEvent.click(screen.getByRole('button', { name: 'rag.openChat' }))

  it('renders toggle button initially', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'rag.openChat' })).toBeInTheDocument()
  })

  it('opens panel when toggle button clicked', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} title="My Bot" />)
    openPanel()
    expect(screen.getByTestId('title')).toHaveTextContent('My Bot')
  })

  it('closes panel when header close button clicked', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    openPanel()
    // Two "Close chat" buttons exist when panel is open: header X and the toggle.
    // The header X button (no aria-expanded) is the first in DOM order.
    const [headerClose] = screen.getAllByRole('button', { name: 'rag.closeChat' })
    fireEvent.click(headerClose)
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })

  it('shows empty state when panel is open with no messages', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    openPanel()
    expect(screen.getByText('rag.emptyState')).toBeInTheDocument()
  })

  it('renders user and assistant messages', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[
          makeMessage('1', 'user', 'Hello'),
          makeMessage('2', 'assistant', 'Hi there!'),
        ]}
      />
    )
    openPanel()
    expect(screen.getByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('Hi there!')).toBeInTheDocument()
  })

  it('calls onSend with trimmed input when send button clicked', async () => {
    const onSend = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onSend={onSend} />)
    openPanel()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'My question' } })
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(onSend).toHaveBeenCalledWith('My question')
  })

  it('clears input after send', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    openPanel()
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'A question' } })
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(input).toHaveValue('')
  })

  it('does not call onSend when input is empty', async () => {
    const onSend = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onSend={onSend} />)
    openPanel()
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not call onSend when input is whitespace only', async () => {
    const onSend = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onSend={onSend} />)
    openPanel()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '   ' } })
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('submits on Enter key press', async () => {
    const onSend = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onSend={onSend} />)
    openPanel()
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Enter submit' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSend).toHaveBeenCalledWith('Enter submit')
  })

  it('does not submit on Shift+Enter', async () => {
    const onSend = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onSend={onSend} />)
    openPanel()
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Shift enter' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('shows typing indicator when isLoading', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} isLoading />)
    openPanel()
    expect(screen.getByLabelText('rag.typingAriaLabel')).toBeInTheDocument()
  })

  it('disables send button and input when isLoading', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} isLoading />)
    openPanel()
    expect(screen.getByTestId('send-btn')).toBeDisabled()
    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('calls onNewChat when new chat button clicked', async () => {
    const onNewChat = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} onNewChat={onNewChat} />)
    openPanel()
    fireEvent.click(screen.getByTestId('new-chat-btn'))
    expect(onNewChat).toHaveBeenCalled()
  })

  it('does not render new chat button when onNewChat not provided', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    openPanel()
    expect(screen.queryByTestId('new-chat-btn')).not.toBeInTheDocument()
  })

  it('renders external link for source without public_article_id', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'An answer')]}
        messageSources={{
          msg1: [{ id: 's1', title: 'Source A', url: 'https://example.com', public_article_id: null }],
        }}
      />
    )
    openPanel()
    const link = screen.getByRole('link', { name: /Source A/ })
    expect(link).toHaveAttribute('href', 'https://example.com')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders internal article button for source with public_article_id', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'An answer')]}
        messageSources={{
          msg1: [{ id: 's2', title: 'Internal Article', url: 'https://example.com', public_article_id: 'pub-123' }],
        }}
      />
    )
    openPanel()
    expect(screen.getByRole('button', { name: /Internal Article/ })).toBeInTheDocument()
  })

  it('calls fetchArticleById when internal source button clicked', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'An answer')]}
        messageSources={{
          msg1: [{ id: 's2', title: 'Internal Article', url: 'https://example.com', public_article_id: 'pub-123' }],
        }}
      />
    )
    openPanel()
    fireEvent.click(screen.getByRole('button', { name: /Internal Article/ }))
    await waitFor(() => {
      expect(mockFetchArticleById).toHaveBeenCalledWith('pub-123', 'zh-TW')
    })
  })

  it('uses url as display text when source title is null', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'An answer')]}
        messageSources={{
          msg1: [{ id: 's3', title: null, url: 'https://example.com/article', public_article_id: null }],
        }}
      />
    )
    openPanel()
    expect(screen.getByRole('link', { name: /https:\/\/example.com\/article/ })).toBeInTheDocument()
  })

  it('renders bold markdown inside assistant message', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'assistant', 'This is **bold** text')]}
      />
    )
    openPanel()
    const bold = screen.getByText('bold')
    expect(bold.tagName).toBe('STRONG')
  })

  it('applies custom placeholder to input', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} placeholder="Ask anything…" />)
    openPanel()
    expect(screen.getByPlaceholderText('Ask anything…')).toBeInTheDocument()
  })

  it('calls onAbort when Escape pressed while open and loading', async () => {
    const onAbort = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} isLoading onAbort={onAbort} />)
    openPanel()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onAbort).toHaveBeenCalled()
  })

  it('does not call onAbort when panel is closed', async () => {
    const onAbort = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} isLoading onAbort={onAbort} />)
    // Do not open panel — Escape should not trigger abort
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onAbort).not.toHaveBeenCalled()
  })

  it('does not call onAbort when not loading', async () => {
    const onAbort = vi.fn()
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} isLoading={false} onAbort={onAbort} />)
    openPanel()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onAbort).not.toHaveBeenCalled()
  })

  it('renders list items from markdown bullet points in assistant message', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'assistant', '- First item\n- Second item')]}
      />
    )
    openPanel()
    expect(screen.getByText('First item')).toBeInTheDocument()
    expect(screen.getByText('Second item')).toBeInTheDocument()
    expect(document.querySelector('ul')).toBeInTheDocument()
  })

  it('renders [N] citation button inline in assistant message', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'See [1] for details')]}
        messageSources={{
          msg1: [{ id: 's1', title: 'Cited Paper', url: 'https://example.com', public_article_id: null }],
        }}
      />
    )
    openPanel()
    // citation button renders the reference number
    expect(screen.getByTitle('Cited Paper')).toBeInTheDocument()
  })

  it('renders [Title] citation as button for source with public_article_id', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', '[Cited Paper] was relevant')]}
        messageSources={{
          msg1: [{ id: 's2', title: 'Cited Paper', url: 'https://example.com', public_article_id: 'pub-abc' }],
        }}
      />
    )
    openPanel()
    // inline citation should render as a clickable button (has public_article_id)
    const citationBtn = screen.getByRole('button', { name: 'Cited Paper' })
    expect(citationBtn).toBeInTheDocument()
  })

  it('renders [Title] citation as link for source without public_article_id', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', '[External Paper] was cited')]}
        messageSources={{
          msg1: [{ id: 's3', title: 'External Paper', url: 'https://external.com', public_article_id: null }],
        }}
      />
    )
    openPanel()
    const citationLink = screen.getByRole('link', { name: 'External Paper' })
    expect(citationLink).toHaveAttribute('href', 'https://external.com')
  })

  it('highlights source chip and scrolls to it when [N] citation clicked', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('msg1', 'assistant', 'See [1] for details')]}
        messageSources={{
          msg1: [{ id: 's1', title: 'Paper A', url: 'https://example.com', public_article_id: null }],
        }}
      />
    )
    openPanel()
    const citationBtn = screen.getByTitle('Paper A')
    fireEvent.click(citationBtn)
    // The source chip should now have highlighted border classes
    await waitFor(() => {
      const link = screen.getByRole('link', { name: /Paper A/ })
      expect(link.className).toMatch(/border-blue-500/)
    })
  })

  it('renders markdown link [text](url) as anchor', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'assistant', 'Visit [Google](https://google.com) for more')]}
      />
    )
    openPanel()
    const link = screen.getByRole('link', { name: 'Google' })
    expect(link).toHaveAttribute('href', 'https://google.com')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('shows timestamp below user messages', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'user', 'Hello')]}
      />
    )
    openPanel()
    // toLocaleTimeString format varies but time should be present
    expect(document.querySelector('[class*="text-\\[10px\\]"]')).toBeTruthy()
  })

  it('shows empty placeholder (…) when assistant message content is empty', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'assistant', '')]}
      />
    )
    openPanel()
    // Empty assistant content renders the placeholder ellipsis
    expect(document.querySelector('.opacity-40')).toBeTruthy()
  })

  it('shows thinking toggle button for assistant message with thinking content', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[{
          id: '1',
          role: 'assistant',
          content: 'Here is my answer.',
          thinking: 'Let me think about this carefully...',
          timestamp: new Date('2024-01-01T10:00:00'),
        }]}
      />
    )
    openPanel()
    // t('rag.thinkingToggle') returns the key itself in this mock
    expect(screen.getByRole('button', { name: /rag\.thinkingToggle/ })).toBeInTheDocument()
  })

  it('hides thinking content by default (collapsed state)', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[{
          id: '1',
          role: 'assistant',
          content: 'Answer',
          thinking: 'My inner thoughts',
          timestamp: new Date('2024-01-01T10:00:00'),
        }]}
      />
    )
    openPanel()
    expect(screen.queryByText('My inner thoughts')).not.toBeInTheDocument()
  })

  it('shows thinking content when thinking toggle is clicked', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[{
          id: '1',
          role: 'assistant',
          content: 'Answer',
          thinking: 'My inner thoughts',
          timestamp: new Date('2024-01-01T10:00:00'),
        }]}
      />
    )
    openPanel()
    fireEvent.click(screen.getByRole('button', { name: /rag\.thinkingToggle/ }))
    expect(screen.getByText('My inner thoughts')).toBeInTheDocument()
  })

  it('collapses thinking content when toggle clicked twice', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[{
          id: '1',
          role: 'assistant',
          content: 'Answer',
          thinking: 'Hidden thoughts',
          timestamp: new Date('2024-01-01T10:00:00'),
        }]}
      />
    )
    openPanel()
    const toggle = screen.getByRole('button', { name: /rag\.thinkingToggle/ })
    fireEvent.click(toggle)
    expect(screen.getByText('Hidden thoughts')).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.queryByText('Hidden thoughts')).not.toBeInTheDocument()
  })

  it('does not show thinking block for assistant messages without thinking', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[makeMessage('1', 'assistant', 'Normal answer')]}
      />
    )
    openPanel()
    expect(screen.queryByRole('button', { name: /rag\.thinkingToggle/ })).not.toBeInTheDocument()
  })

  it('does not show thinking block for user messages', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(
      <FloatingChatbotPanel
        {...defaultProps}
        messages={[{
          id: '1',
          role: 'user',
          content: 'User question',
          thinking: 'Should not show',
          timestamp: new Date('2024-01-01T10:00:00'),
        }]}
      />
    )
    openPanel()
    expect(screen.queryByRole('button', { name: /rag\.thinkingToggle/ })).not.toBeInTheDocument()
    expect(screen.queryByText('Should not show')).not.toBeInTheDocument()
  })
})
