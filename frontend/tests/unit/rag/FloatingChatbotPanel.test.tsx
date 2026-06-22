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

  const openPanel = () => fireEvent.click(screen.getByRole('button', { name: 'Open chat' }))

  it('renders toggle button initially', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Open chat' })).toBeInTheDocument()
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
    const [headerClose] = screen.getAllByRole('button', { name: 'Close chat' })
    fireEvent.click(headerClose)
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })

  it('shows empty state when panel is open with no messages', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    render(<FloatingChatbotPanel {...defaultProps} />)
    openPanel()
    expect(screen.getByText('Start a conversation.')).toBeInTheDocument()
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
    expect(screen.getByLabelText('Agent is typing')).toBeInTheDocument()
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
})
