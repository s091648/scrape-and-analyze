import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChat } from '@s091648/chatbot-plugin-ui'

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
  useGuestMode: vi.fn().mockReturnValue({ isGuestMode: true }),
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
}))

vi.mock('sonner', () => ({
  toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

const mockSendMessage = vi.fn()
const mockClearMessages = vi.fn()

// Mock the custom panel so we can inspect what props FloatingChatbotWrapper passes
vi.mock('@/components/features/chat/FloatingChatbotPanel', () => ({
  FloatingChatbotPanel: vi.fn(({ messages, onSend, isLoading, title, onNewChat }: any) => (
    <div data-testid="chatbot-plugin">
      <div data-testid="title">{title}</div>
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
}))

vi.mock('@s091648/chatbot-plugin-ui', () => ({
  openaiAdapter: {
    buildRequest: vi.fn(),
    parse: vi.fn().mockReturnValue(null),
  },
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
  })

  it('renders chatbot panel', async () => {
    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('chatbot-plugin')).toBeInTheDocument()
  })

  it('calls sendMessage when send button clicked', async () => {
    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockSendMessage).toHaveBeenCalledWith('test message')
  })

  it('does not call sendMessage when text is blank', async () => {
    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    vi.mocked(FloatingChatbotPanel).mockImplementationOnce(({ onSend }: any) => (
      <button data-testid="blank-send" onClick={() => onSend('   ')}>Blank</button>
    ))

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
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
      '@/components/features/chat/FloatingChatbotWrapper'
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
      '@/components/features/chat/FloatingChatbotWrapper'
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
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    await waitFor(() => {
      expect(setItemSpy).toHaveBeenCalled()
    })
    setItemSpy.mockRestore()
  })

  it('renders nothing while session is loading', async () => {
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'loading', update: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    const { container } = render(<FloatingChatbotWrapper />)
    expect(container.firstChild).toBeNull()
  })

  it('renders chatbot for unauthenticated (guest) users', async () => {
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('chatbot-plugin')).toBeInTheDocument()
  })

  it('clears localStorage when user logs out', async () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    await waitFor(() => {
      expect(removeItemSpy).toHaveBeenCalledWith('rag_float_chat_messages')
    })
    removeItemSpy.mockRestore()
  })

  it('passes theme prop to FloatingChatbotPanel', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'dark', theme: 'dark', cycleMode: mockCycleMode, setMode: vi.fn() })

    const { FloatingChatbotPanel } = await import('@/components/features/chat/FloatingChatbotPanel')
    let receivedTheme: string | undefined
    vi.mocked(FloatingChatbotPanel).mockImplementationOnce(({ theme, messages, onSend, isLoading, onNewChat }: any) => {
      receivedTheme = theme
      return (
        <div data-testid="chatbot-plugin">
          <button data-testid="new-chat-btn" onClick={onNewChat}>New</button>
        </div>
      )
    })

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(receivedTheme).toBe('dark')
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
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('new-chat-btn'))

    expect(mockClearMessages).toHaveBeenCalled()
    expect(removeItemSpy).toHaveBeenCalledWith('rag_float_chat_messages')
    removeItemSpy.mockRestore()
  })

  it('hides chatbot for unauthenticated non-guest users', async () => {
    const { useGuestMode } = await import('@/lib/providers')
    vi.mocked(useGuestMode).mockReturnValueOnce({ isGuestMode: false })
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    const { container } = render(<FloatingChatbotWrapper />)
    expect(container.firstChild).toBeNull()
  })

  it('shows toast.error on 503 via onError callback', async () => {
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
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    capturedOnError?.(new Error('HTTP 503'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('問答服務暫時無法使用，請稍後再試')
  })

  it('shows toast.error on generic error via onError callback', async () => {
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
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    capturedOnError?.(new Error('unexpected failure'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('發生錯誤，請稍後再試')
  })

  it('shows quota suffix in title when quota has remaining >= 0', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValueOnce({ quota: { remaining: 3, limit: 10 }, refreshQuota: vi.fn() })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('title').textContent).toContain('3/10')
  })

  it('does not show quota suffix in title when quota is null', async () => {
    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('title').textContent).not.toContain('/')
  })

  it('customAdapter maps {"thinking":"..."} SSE line to thinking_delta event', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: vi.fn(), isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)

    const line = 'data: {"thinking": "Let me reason through this"}'
    const event = capturedAdapter.parse(line)
    expect(event).toEqual({ type: 'thinking_delta', content: 'Let me reason through this' })
  })

  it('customAdapter returns null for {"sources":[...]} SSE line (handled via side-effect)', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: vi.fn(), isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { FloatingChatbotWrapper } = await import(
      '@/components/features/chat/FloatingChatbotWrapper'
    )
    render(<FloatingChatbotWrapper />)

    const line = 'data: {"sources": [{"id":"s1","title":"Paper","url":"https://example.com","public_article_id":null}]}'
    const event = capturedAdapter.parse(line)
    expect(event).toBeNull()
  })
})
