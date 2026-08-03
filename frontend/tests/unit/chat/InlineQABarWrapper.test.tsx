import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { useChat, AgentInput } from '@s091648/chatbot-plugin-ui'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: 'unauthenticated' }),
}))

const zhTW: Record<string, string> = {
  'rag.rateLimitError': '已達每日問答上限',
  'rag.serviceUnavailable': '問答服務暫時無法使用，請稍後再試',
  'rag.genericError': '發生錯誤，請稍後再試',
  'rag.thinking': '思考中…',
  'rag.placeholder': '詢問 AI：最近有哪些相關研究？',
  'rag.agentInputAriaLabel': '輸入問題',
  'rag.agentSendAriaLabel': '傳送',
  'rag.agentSend': '執行',
  'rag.agentSendLoading': '執行中...',
  'rag.toolStatusRunning': '執行中',
  'rag.toolStatusDone': '完成',
  'rag.toolStatusError': '錯誤',
  'rag.previousTurn': '上一則問題',
  'rag.nextTurn': '下一則問題',
}

const mockCycleMode = vi.fn()
const mockRemovePinnedArticle = vi.fn()
const mockToggleGroupArticle = vi.fn()
const mockRemoveGroup = vi.fn()
vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
  useI18n: vi.fn().mockReturnValue({
    t: (k: string, params?: Record<string, any>) => {
      if (k === 'rag.weeklyGroupPill') return `${params?.date} · ${params?.count} articles`
      return zhTW[k] ?? k
    },
  }),
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() }),
  useAuthToken: vi.fn().mockReturnValue({ token: undefined, isLoading: false }),
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
  usePinnedReport: vi.fn().mockReturnValue({
    pinnedArticles: [],
    removePinnedArticle: mockRemovePinnedArticle,
    pinnedGroups: [],
    toggleGroupArticle: mockToggleGroupArticle,
    removeGroup: mockRemoveGroup,
    isPinned: (_id: string) => false,
  }),
}))

vi.mock('sonner', () => ({
  toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

const mockSendMessage = vi.fn()
const mockMessages = [
  { id: '1', role: 'user', content: 'hello', timestamp: new Date() },
  { id: '2', role: 'assistant', content: 'Hi there!', timestamp: new Date() },
]

vi.mock('@s091648/chatbot-plugin-ui', () => ({
  AgentInput: vi.fn(({ onSend, isLoading, placeholder }: any) => (
    <div>
      <input
        data-testid="agent-input"
        placeholder={placeholder}
        disabled={isLoading}
        onChange={() => {}}
      />
      <button data-testid="send-btn" onClick={() => onSend('test question')}>
        Send
      </button>
    </div>
  )),
  openaiAdapter: {},
  useChat: vi.fn(),
}))

describe('InlineQABarWrapper', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (_id: string) => false,
    } as any)
    vi.mocked(AgentInput).mockImplementation(({ onSend, isLoading, placeholder }: any) => (
      <div>
        <input
          data-testid="agent-input"
          placeholder={placeholder}
          disabled={isLoading}
          onChange={() => {}}
        />
        <button data-testid="send-btn" onClick={() => onSend('test question')}>
          Send
        </button>
      </div>
    ))
  })

  it('renders AgentInput', async () => {
    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    expect(screen.getByTestId('agent-input')).toBeInTheDocument()
  })

  it('calls sendMessage when send button clicked with non-empty text', async () => {
    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockSendMessage).toHaveBeenCalledWith('test question')
  })

  it('does not call sendMessage when text is blank', async () => {
    vi.mocked(AgentInput).mockImplementationOnce(({ onSend }: any) => (
      <button data-testid="blank-send" onClick={() => onSend('   ')}>
        Blank
      </button>
    ))

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    const btn = screen.queryByTestId('blank-send')
    if (btn) fireEvent.click(btn)
    expect(mockSendMessage).not.toHaveBeenCalled()
  })

  // AnswerDisplay is no longer rendered by InlineQABarWrapper itself (2026-07-15) — the wrapper
  // now only owns the chat state and reports it upward via onConversationChange, so a wrapping
  // component (WeeklyReportWidget) can render the answer panel elsewhere in the tree without
  // this input bar ever unmounting. These tests assert on the reported snapshot instead of DOM
  // text; AnswerDisplay's own rendering of that snapshot is covered by AnswerDisplay.test.tsx.

  it('reports paired turns via onConversationChange when messages include an assistant reply', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: mockMessages,
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)

    await waitFor(() => {
      const snapshot = onConversationChange.mock.calls.at(-1)?.[0]
      expect(snapshot?.turns).toHaveLength(1)
      expect(snapshot?.turns[0].assistantMessage.content).toBe('Hi there!')
      expect(snapshot?.turns[0].userMessage?.content).toBe('hello')
    })
  })

  it('reports isLoading true via onConversationChange while a response is streaming', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: mockMessages,
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: vi.fn(),
    })
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)

    const snapshot = onConversationChange.mock.calls.at(-1)?.[0]
    expect(snapshot?.isLoading).toBe(true)
    expect(snapshot?.currentIndex).toBe(snapshot?.turns.length - 1)
  })

  it('passes mode from useTheme as theme prop to AgentInput', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'dark', theme: 'dark', cycleMode: mockCycleMode, setMode: vi.fn() })

    let receivedTheme: string | undefined
    vi.mocked(AgentInput).mockImplementationOnce(({ theme, onSend, placeholder }: any) => {
      receivedTheme = theme
      return <button data-testid="send-btn" onClick={() => onSend('x')}>Send</button>
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(receivedTheme).toBe('dark')
  })

  it('passes "auto" mode as theme prop when mode is auto', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() })

    let receivedTheme: string | undefined
    vi.mocked(AgentInput).mockImplementationOnce(({ theme, onSend }: any) => {
      receivedTheme = theme
      return <button data-testid="send-btn" onClick={() => onSend('x')}>Send</button>
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(receivedTheme).toBe('auto')
  })

  it('reports the error via onConversationChange on 429', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: new Error('HTTP 429'),
      clearMessages: vi.fn(),
    })
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)
    const snapshot = onConversationChange.mock.calls.at(-1)?.[0]
    expect(snapshot?.error?.message).toBe('HTTP 429')
  })

  it('shows toast.warning on 429 via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    capturedOnError?.(new Error('HTTP 429'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.warning)).toHaveBeenCalledWith('已達每日問答上限')
  })

  it('shows toast.error on 503 via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    capturedOnError?.(new Error('HTTP 503'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('問答服務暫時無法使用，請稍後再試')
  })

  it('shows toast.error on generic error via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    capturedOnError?.(new Error('Network error'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('發生錯誤，請稍後再試')
  })

  it('shows quota text when quota has remaining >= 0', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValue({
      quota: { remaining: 5, limit: 10 },
      refreshQuota: vi.fn(),
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.getByText(/5 \/ 10/)).toBeInTheDocument()
    expect(screen.getByText(/rag\.remainingRequests/)).toBeInTheDocument()
  })

  it('does not show quota text when quota is null', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValue({ quota: null, refreshQuota: vi.fn() })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.queryByText(/\/ 10/)).not.toBeInTheDocument()
  })

  it('calls abort when Escape pressed while loading', async () => {
    const mockAbort = vi.fn()
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: vi.fn(),
      abort: mockAbort,
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(mockAbort).toHaveBeenCalled()
  })

  it('does not call abort on non-Escape key while loading', async () => {
    const mockAbort = vi.fn()
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: vi.fn(),
      abort: mockAbort,
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.keyDown(window, { key: 'Enter' })
    expect(mockAbort).not.toHaveBeenCalled()
  })

  it('calls refreshQuota when loading transitions from true to false', async () => {
    const mockRefreshQuota = vi.fn()
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValue({ quota: null, refreshQuota: mockRefreshQuota })

    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: vi.fn(),
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    const { rerender } = render(<InlineQABarWrapper />)

    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)
    rerender(<InlineQABarWrapper />)

    await waitFor(() => {
      expect(mockRefreshQuota).toHaveBeenCalled()
    })
  })

  it('still calls sendMessage as usual when send is triggered', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'assistant', content: 'answer', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockSendMessage).toHaveBeenCalledWith('test question')
  })

  it('customAdapter maps {"thinking":"..."} SSE line to thinking_delta event', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: vi.fn(), isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    const line = 'data: {"thinking": "Reasoning about this"}'
    const event = capturedAdapter.parse(line)
    expect(event).toEqual({ type: 'thinking_delta', content: 'Reasoning about this' })
  })

  it('passes translated labels to AgentInput', async () => {
    let receivedLabels: any
    vi.mocked(AgentInput).mockImplementationOnce(({ labels, onSend }: any) => {
      receivedLabels = labels
      return <button data-testid="send-btn" onClick={() => onSend('x')}>Send</button>
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    expect(receivedLabels).toBeDefined()
    expect(receivedLabels.send).toBe('執行')
    expect(receivedLabels.sendLoading).toBe('執行中...')
    expect(receivedLabels.sendAriaLabel).toBe('傳送')
    expect(receivedLabels.inputAriaLabel).toBe('輸入問題')
    expect(receivedLabels.toolCallCard).toMatchObject({
      statusRunning: '執行中',
      statusDone: '完成',
      statusError: '錯誤',
    })
  })

  // ── Pinning (2026-07-12, US7: pin weekly report into chat) ──────────────

  it('omits X-Pinned-Article-Ids header when no articles are pinned', async () => {
    let capturedHeaders: Record<string, string> | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedHeaders = opts.headers
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(capturedHeaders?.['X-Pinned-Article-Ids']).toBeUndefined()
  })

  it('includes X-Pinned-Article-Ids header built from pinned articles', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      removePinnedArticle: mockRemovePinnedArticle,
    } as any)

    let capturedHeaders: Record<string, string> | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedHeaders = opts.headers
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: vi.fn() }
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(capturedHeaders?.['X-Pinned-Article-Ids']).toBe('a1,a2')
  })

  it('renders a chip for each pinned article and removes it on click', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }],
      removePinnedArticle: mockRemovePinnedArticle,
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.getByText('Paper One')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('rag.removeArticleRef'))
    expect(mockRemovePinnedArticle).toHaveBeenCalledWith('a1')
  })

  it('does not render a pinned chip row when no articles are pinned', async () => {
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.queryByLabelText('rag.removeArticleRef')).not.toBeInTheDocument()
  })

  // ── Group pin pills (2026-07-14, US10) ────────────────────────────────────

  it('renders one group pill with the live included count instead of one pill per article', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [{
        id: 'report-1',
        dateLabel: '6/29',
        articles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      }],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (id: string) => ['a1', 'a2'].includes(id),
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    expect(screen.getByText('6/29 · 2 articles')).toBeInTheDocument()
    expect(screen.queryByText('Paper One')).not.toBeInTheDocument()
  })

  it('renders individually-pinned articles alongside a group pill', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }, { id: 'a9', title: 'Solo Paper' }],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [{ id: 'report-1', dateLabel: '6/29', articles: [{ id: 'a1', title: 'Paper One' }] }],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (id: string) => id === 'a1' || id === 'a9',
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    expect(screen.getByText('6/29 · 1 articles')).toBeInTheDocument()
    expect(screen.getByText('Solo Paper')).toBeInTheDocument()
  })

  it('removes the whole batch when the group pill\'s remove icon is clicked', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [{ id: 'report-1', dateLabel: '6/29', articles: [{ id: 'a1', title: 'Paper One' }] }],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (id: string) => id === 'a1',
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    fireEvent.click(screen.getByLabelText('rag.removeArticleRef'))
    expect(mockRemoveGroup).toHaveBeenCalledWith('report-1')
  })

  it('toggles an article via the edit popover checklist', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [{
        id: 'report-1',
        dateLabel: '6/29',
        articles: [{ id: 'a1', title: 'Paper One' }, { id: 'a2', title: 'Paper Two' }],
      }],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (id: string) => ['a1', 'a2'].includes(id),
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    fireEvent.click(screen.getByLabelText('rag.editGroupArticles'))
    const checkbox = await screen.findByText('Paper Two')
    const row = checkbox.closest('label')!
    fireEvent.click(row.querySelector('button[role="checkbox"]')!)

    expect(mockToggleGroupArticle).toHaveBeenCalledWith('report-1', 'a2')
  })

  // ── onMessageSent + multi-turn pairing (2026-07-14) ───────────────────────

  it('calls onMessageSent when a message is sent', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)
    const onMessageSent = vi.fn()

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper onMessageSent={onMessageSent} />)
    fireEvent.click(screen.getByTestId('send-btn'))

    expect(onMessageSent).toHaveBeenCalled()
  })

  it('does not throw when onMessageSent is omitted', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(() => fireEvent.click(screen.getByTestId('send-btn'))).not.toThrow()
  })

  it('pairs consecutive user/assistant messages into turns and reports the newest as current by default', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: 'u1', role: 'user', content: 'First question', timestamp: new Date() },
        { id: 'a1', role: 'assistant', content: 'First answer', timestamp: new Date() },
        { id: 'u2', role: 'user', content: 'Second question', timestamp: new Date() },
        { id: 'a2', role: 'assistant', content: 'Second answer', timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)

    const snapshot = onConversationChange.mock.calls.at(-1)?.[0]
    expect(snapshot?.turns.map((t: any) => t.assistantMessage.content)).toEqual(['First answer', 'Second answer'])
    expect(snapshot?.currentIndex).toBe(1)
  })

  it('onPrevTurn/onNextTurn from the reported snapshot move currentIndex without changing the turns themselves', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: 'u1', role: 'user', content: 'First question', timestamp: new Date() },
        { id: 'a1', role: 'assistant', content: 'First answer', timestamp: new Date() },
        { id: 'u2', role: 'user', content: 'Second question', timestamp: new Date() },
        { id: 'a2', role: 'assistant', content: 'Second answer', timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    } as any)
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)

    const latest = onConversationChange.mock.calls.at(-1)?.[0]
    expect(latest.currentIndex).toBe(1)

    act(() => { latest.onPrevTurn() })

    await waitFor(() => {
      const afterPrev = onConversationChange.mock.calls.at(-1)?.[0]
      expect(afterPrev.currentIndex).toBe(0)
      expect(afterPrev.turns).toHaveLength(2)
    })
  })
})
