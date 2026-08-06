import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useSession } from 'next-auth/react'

// FloatingChatbotWrapper is now a thin presentational consumer of useFloatChat() (see
// lib/providers/float-chat-provider.tsx) — the actual useChat()/localStorage/adapter/toast
// logic that used to live here is now covered by tests/unit/providers/float-chat-provider.test.tsx.
// This file only covers what the wrapper itself still owns: guest-mode visibility gating and
// prop passthrough to FloatingChatbotPanel.

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: { accessToken: 'tok' }, status: 'authenticated' }),
}))

const zhTW: Record<string, string> = {
  'rag.placeholder': '詢問 AI：最近有哪些相關研究？',
  'rag.assistantTitle': 'AI 助理',
}

const mockCycleMode = vi.fn()
const mockSetChatOpen = vi.fn()
const mockOnSend = vi.fn()
const mockOnNewChat = vi.fn()
const mockOnAbort = vi.fn()
const mockRemovePinnedArticle = vi.fn()

function defaultFloatChat() {
  return {
    messages: [],
    messageSources: {},
    messageAttachments: {},
    isLoading: false,
    chatOpen: false,
    setChatOpen: mockSetChatOpen,
    onSend: mockOnSend,
    onNewChat: mockOnNewChat,
    onAbort: mockOnAbort,
  }
}

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k }),
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() }),
  useGuestMode: vi.fn().mockReturnValue({ isGuestMode: true }),
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
  usePinnedArticle: vi.fn().mockReturnValue({
    pinnedArticles: [],
    removePinnedArticle: mockRemovePinnedArticle,
  }),
  useFloatChat: vi.fn(),
}))

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

describe('FloatingChatbotWrapper', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { useFloatChat } = await import('@/lib/providers')
    vi.mocked(useFloatChat).mockReturnValue(defaultFloatChat() as any)
  })

  it('renders chatbot panel', async () => {
    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('chatbot-plugin')).toBeInTheDocument()
  })

  it('delegates send button clicks to the context onSend', async () => {
    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockOnSend).toHaveBeenCalledWith('test message')
  })

  it('shows multiple messages when conversation has multiple turns', async () => {
    const { useFloatChat } = await import('@/lib/providers')
    vi.mocked(useFloatChat).mockReturnValue({
      ...defaultFloatChat(),
      messages: [
        { id: '1', role: 'user', content: 'q1', timestamp: new Date() },
        { id: '2', role: 'assistant', content: 'a1', timestamp: new Date() },
        { id: '3', role: 'user', content: 'q2', timestamp: new Date() },
        { id: '4', role: 'assistant', content: 'a2', timestamp: new Date() },
      ],
    } as any)

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('message-count').textContent).toBe('4')
  })

  it('renders nothing while session is loading', async () => {
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'loading', update: vi.fn() } as any)

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    const { container } = render(<FloatingChatbotWrapper />)
    expect(container.firstChild).toBeNull()
  })

  it('renders chatbot for unauthenticated (guest) users', async () => {
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() } as any)

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('chatbot-plugin')).toBeInTheDocument()
  })

  it('hides chatbot for unauthenticated non-guest users', async () => {
    const { useGuestMode } = await import('@/lib/providers')
    vi.mocked(useGuestMode).mockReturnValueOnce({ isGuestMode: false } as any)
    vi.mocked(useSession).mockReturnValueOnce({ data: null, status: 'unauthenticated', update: vi.fn() } as any)

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    const { container } = render(<FloatingChatbotWrapper />)
    expect(container.firstChild).toBeNull()
  })

  it('passes theme prop to FloatingChatbotPanel', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'dark', theme: 'dark', cycleMode: mockCycleMode, setMode: vi.fn() } as any)

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

  it('delegates onNewChat to the context', async () => {
    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    fireEvent.click(screen.getByTestId('new-chat-btn'))
    expect(mockOnNewChat).toHaveBeenCalled()
  })

  it('shows quota suffix in title when quota has remaining >= 0', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValueOnce({ quota: { remaining: 3, limit: 10 }, refreshQuota: vi.fn() } as any)

    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('title').textContent).toContain('3/10')
  })

  it('does not show quota suffix in title when quota is null', async () => {
    const { FloatingChatbotWrapper } = await import('@/components/features/chat/FloatingChatbotWrapper')
    render(<FloatingChatbotWrapper />)
    expect(screen.getByTestId('title').textContent).not.toContain('/')
  })
})
