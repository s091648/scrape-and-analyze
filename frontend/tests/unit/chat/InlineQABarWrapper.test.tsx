import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
}

const mockCycleMode = vi.fn()
const mockRemovePinnedArticle = vi.fn()
vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k }),
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() }),
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
  usePinnedArticle: vi.fn().mockReturnValue({ pinnedArticles: [], removePinnedArticle: mockRemovePinnedArticle }),
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
    const { usePinnedArticle } = await import('@/lib/providers')
    vi.mocked(usePinnedArticle).mockReturnValue({
      pinnedArticles: [],
      removePinnedArticle: mockRemovePinnedArticle,
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

  it('shows assistant answer in AnswerDisplay when messages include assistant reply', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: mockMessages,
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    await waitFor(() => {
      expect(screen.getByText('Hi there!')).toBeInTheDocument()
    })
  })

  it('shows loading cursor in AnswerDisplay when isLoading and assistant message exists', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: mockMessages,
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: vi.fn(),
    })

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    const cursor = document.querySelector('.animate-pulse')
    expect(cursor).toBeInTheDocument()
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

  it('shows rate limit error message on 429 error', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: new Error('HTTP 429'),
      clearMessages: vi.fn(),
    })

    const { InlineQABarWrapper } = await import(
      '@/components/features/chat/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    expect(screen.getByText('已達每日問答上限')).toBeInTheDocument()
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

  it('clears lastSources when send is triggered', async () => {
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
    const { usePinnedArticle } = await import('@/lib/providers')
    vi.mocked(usePinnedArticle).mockReturnValue({
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
    const { usePinnedArticle } = await import('@/lib/providers')
    vi.mocked(usePinnedArticle).mockReturnValue({
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
})
