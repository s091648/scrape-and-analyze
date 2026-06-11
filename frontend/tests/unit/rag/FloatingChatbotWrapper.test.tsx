import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChat, ChatbotPlugin } from '@Teng91/chatbot-plugin-ui'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: 'unauthenticated' }),
}))

vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
}))

vi.mock('sonner', () => ({
  toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

const mockSendMessage = vi.fn()

vi.mock('@Teng91/chatbot-plugin-ui', () => ({
  ChatbotPlugin: vi.fn(({ messages, onSend, isLoading, title }: any) => (
    <div data-testid="chatbot-plugin">
      <div data-testid="title">{title}</div>
      <button data-testid="fab" aria-label="Open chat" onClick={() => {}}>
        FAB
      </button>
      <div data-testid="message-count">{messages.length}</div>
      <button
        data-testid="send-btn"
        disabled={isLoading}
        onClick={() => onSend('test message')}
      >
        Send
      </button>
    </div>
  )),
  openaiAdapter: {},
  useChat: vi.fn(),
}))

describe('FloatingChatbotWrapper', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })
    vi.mocked(ChatbotPlugin).mockImplementation(({ messages, onSend, isLoading, title }: any) => (
      <div data-testid="chatbot-plugin">
        <div data-testid="title">{title}</div>
        <button data-testid="fab" aria-label="Open chat" onClick={() => {}}>
          FAB
        </button>
        <div data-testid="message-count">{messages.length}</div>
        <button
          data-testid="send-btn"
          disabled={isLoading}
          onClick={() => onSend('test message')}
        >
          Send
        </button>
      </div>
    ))
  })

  it('renders ChatbotPlugin component', async () => {
    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('chatbot-plugin')).toBeInTheDocument()
  })

  it('calls sendMessage when send button clicked', async () => {
    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockSendMessage).toHaveBeenCalledWith('test message')
  })

  it('does not call sendMessage when text is blank', async () => {
    vi.mocked(ChatbotPlugin).mockImplementationOnce(({ onSend }: any) => (
      <button data-testid="blank-send" onClick={() => onSend('   ')}>
        Blank
      </button>
    ))

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    const btn = screen.queryByTestId('blank-send')
    if (btn) fireEvent.click(btn)
    expect(mockSendMessage).not.toHaveBeenCalled()
  })

  it('shows multiple messages when conversation has multiple turns', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: '1', role: 'user', content: 'q1', timestamp: new Date() },
        { id: '2', role: 'assistant', content: 'a1', timestamp: new Date() },
        { id: '3', role: 'user', content: 'q2', timestamp: new Date() },
        { id: '4', role: 'assistant', content: 'a2', timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('message-count').textContent).toBe('4')
  })

  it('shows toast warning on 429 error', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return {
        messages: [],
        sendMessage: mockSendMessage,
        isLoading: false,
        error: null,
        clearMessages: vi.fn(),
      }
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    capturedOnError?.(new Error('HTTP 429'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.warning)).toHaveBeenCalledWith('已達每日問答上限')
  })

  it('saves messages to sessionStorage when messages update', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    await waitFor(() => {
      expect(setItemSpy).toHaveBeenCalled()
    })
    setItemSpy.mockRestore()
  })
})
