import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChat, ChatbotPlugin } from '@s091648/chatbot-plugin-ui'

import { useSession } from 'next-auth/react'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: { accessToken: 'tok' }, status: 'authenticated' }),
}))

const zhTW: Record<string, string> = {
  'rag.rateLimitError': '已達每日問答上限',
  'rag.serviceUnavailable': '問答服務暫時無法使用，請稍後再試',
  'rag.genericError': '發生錯誤，請稍後再試',
  'rag.thinking': '思考中…',
  'rag.placeholder': '詢問 AI：最近有哪些相關研究？',
  'rag.assistantTitle': 'AI 助理',
}

const mockCycleMode = vi.fn()
vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k }),
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() }),
}))

vi.mock('sonner', () => ({
  toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

const mockSendMessage = vi.fn()
const mockClearMessages = vi.fn()

vi.mock('@s091648/chatbot-plugin-ui', () => ({
  ChatbotPlugin: vi.fn(({ messages, onSend, isLoading, title, onNewChat }: any) => (
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
      {onNewChat && (
        <button data-testid="new-chat-btn" onClick={onNewChat}>
          New Chat
        </button>
      )}
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
      clearMessages: mockClearMessages,
    })
    vi.mocked(ChatbotPlugin).mockImplementation(({ messages, onSend, isLoading, title, onNewChat }: any) => (
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
        {onNewChat && (
          <button data-testid="new-chat-btn" onClick={onNewChat}>
            New Chat
          </button>
        )}
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
      clearMessages: mockClearMessages,
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
        clearMessages: mockClearMessages,
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

  it('saves messages to localStorage when messages update', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
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

  it('renders nothing when user is not authenticated', async () => {
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    const { container } = render(<FloatingChatbotWrapper />)
    expect(container.firstChild).toBeNull()
  })

  it('passes mode from useTheme as theme prop to ChatbotPlugin', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'dark', theme: 'dark', cycleMode: mockCycleMode, setMode: vi.fn() })

    let receivedTheme: string | undefined
    vi.mocked(ChatbotPlugin).mockImplementationOnce(({ theme, messages, onSend, isLoading, title, onNewChat }: any) => {
      receivedTheme = theme
      return (
        <div data-testid="chatbot-plugin">
          <button data-testid="new-chat-btn" onClick={onNewChat}>New</button>
        </div>
      )
    })

    const { FloatingChatbotWrapper } = await import('@/components/features/rag/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(receivedTheme).toBe('dark')
  })

  it('passes "light" mode as theme prop when mode is light', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'light', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() })

    let receivedTheme: string | undefined
    vi.mocked(ChatbotPlugin).mockImplementationOnce(({ theme }: any) => {
      receivedTheme = theme
      return <div data-testid="chatbot-plugin" />
    })

    const { FloatingChatbotWrapper } = await import('@/components/features/rag/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(receivedTheme).toBe('light')
  })

  it('passes "auto" mode as theme prop when mode is auto', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() })

    let receivedTheme: string | undefined
    vi.mocked(ChatbotPlugin).mockImplementationOnce(({ theme }: any) => {
      receivedTheme = theme
      return <div data-testid="chatbot-plugin" />
    })

    const { FloatingChatbotWrapper } = await import('@/components/features/rag/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(receivedTheme).toBe('auto')
  })

  it('clears messages and localStorage when onNewChat is triggered', async () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/rag/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('new-chat-btn'))

    expect(mockClearMessages).toHaveBeenCalled()
    expect(removeItemSpy).toHaveBeenCalledWith('rag_float_chat_messages')
    removeItemSpy.mockRestore()
  })
})
