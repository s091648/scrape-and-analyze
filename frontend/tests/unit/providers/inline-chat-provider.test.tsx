import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { useChat } from '@s091648/chatbot-plugin-ui'
import { useSession } from 'next-auth/react'
import { InlineChatProvider, useInlineChat } from '@/lib/providers/inline-chat-provider'
import { usePinnedReport } from '@/lib/providers/pinned-article-provider'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: { user: { id: 'user-1' } }, status: 'authenticated' }),
}))

const zhTW: Record<string, string> = {
  'rag.rateLimitError': '已達每日問答上限',
  'rag.serviceUnavailable': '問答服務暫時無法使用，請稍後再試',
  'rag.genericError': '發生錯誤，請稍後再試',
}

vi.mock('@/lib/providers/i18n-provider', () => ({
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => zhTW[k] ?? k }),
}))
vi.mock('@/lib/providers/topic-provider', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
}))
vi.mock('@/lib/providers/auth-token-provider', () => ({
  useAuthToken: vi.fn().mockReturnValue({ token: 'tok', isLoading: false }),
}))

const { mockRefreshQuota } = vi.hoisted(() => ({ mockRefreshQuota: vi.fn() }))
vi.mock('@/lib/providers/chat-quota-provider', () => ({
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: mockRefreshQuota }),
}))

vi.mock('@/lib/providers/pinned-article-provider', () => ({
  usePinnedReport: vi.fn().mockReturnValue({ pinnedArticles: [] }),
}))

vi.mock('sonner', () => ({
  toast: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

const mockSendMessage = vi.fn()
const mockClearMessages = vi.fn()
const mockAbort = vi.fn()

vi.mock('@s091648/chatbot-plugin-ui', () => ({
  openaiAdapter: {
    buildRequest: vi.fn(),
    parse: vi.fn().mockReturnValue(null),
  },
  useChat: vi.fn(),
}))

function Consumer() {
  const { messages, turns, currentTurnIndex, isLoading, error, hasUnreadResponse, onPrevTurn, onNextTurn, onSend, onAbort } = useInlineChat()
  return (
    <div>
      <span data-testid="message-count">{messages.length}</span>
      <span data-testid="turn-count">{turns.length}</span>
      <span data-testid="current-index">{currentTurnIndex}</span>
      <span data-testid="is-loading">{String(isLoading)}</span>
      <span data-testid="error">{error?.message ?? ''}</span>
      <span data-testid="has-unread">{String(hasUnreadResponse)}</span>
      <span data-testid="turn-0-tool-calls">{JSON.stringify((turns[0]?.toolCalls ?? []).map((m: any) => m.id))}</span>
      <span data-testid="turn-1-tool-calls">{JSON.stringify((turns[1]?.toolCalls ?? []).map((m: any) => m.id))}</span>
      <button data-testid="send" onClick={() => onSend('question')}>send</button>
      <button data-testid="send-blank" onClick={() => onSend('   ')}>send-blank</button>
      <button data-testid="abort" onClick={onAbort}>abort</button>
      <button data-testid="prev" onClick={onPrevTurn}>prev</button>
      <button data-testid="next" onClick={onNextTurn}>next</button>
    </div>
  )
}

function renderProvider() {
  return render(
    <InlineChatProvider>
      <Consumer />
    </InlineChatProvider>
  )
}

describe('InlineChatProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSession).mockReturnValue({ data: { user: { id: 'user-1' } }, status: 'authenticated' } as any)
    vi.mocked(usePinnedReport).mockReturnValue({ pinnedArticles: [] } as any)
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
  })

  it('pairs user/assistant messages into turns and points currentIndex at the newest', async () => {
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
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    renderProvider()
    expect(screen.getByTestId('turn-count').textContent).toBe('2')
    expect(screen.getByTestId('current-index').textContent).toBe('1')
  })

  // Regression: real backend push order (see chatbot-plugin-ui's useChat) appends role:'tool'
  // messages *after* the assistant placeholder they belong to, not before it — so attributing a
  // tool call to the wrong (or no) turn is an easy mistake here. This exercises the exact shape
  // reported by a real user: turn 1 with no tool call, turn 2 with one whose result never
  // resolved into a final assistant reply (empty content).
  it('attributes each tool call to the turn it actually belongs to, matching real backend push order', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: 'u1', role: 'user', content: 'First question', timestamp: new Date() },
        { id: 'a1', role: 'assistant', content: 'First answer', timestamp: new Date() },
        { id: 'u2', role: 'user', content: 'Second question', timestamp: new Date() },
        { id: 'a2', role: 'assistant', content: '', timestamp: new Date() },
        { id: 't2', role: 'tool', content: '', toolCall: { id: 'c2', name: 'search_articles', arguments: {} }, timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    renderProvider()
    expect(screen.getByTestId('turn-0-tool-calls').textContent).toBe('[]')
    expect(screen.getByTestId('turn-1-tool-calls').textContent).toBe('["t2"]')
  })

  it('onSend forwards trimmed text to sendMessage', () => {
    renderProvider()
    fireEvent.click(screen.getByTestId('send'))
    expect(mockSendMessage).toHaveBeenCalledWith('question')
  })

  it('onSend does not call sendMessage for blank text', () => {
    renderProvider()
    fireEvent.click(screen.getByTestId('send-blank'))
    expect(mockSendMessage).not.toHaveBeenCalled()
  })

  it('onAbort delegates to useChat().abort', () => {
    renderProvider()
    fireEvent.click(screen.getByTestId('abort'))
    expect(mockAbort).toHaveBeenCalled()
  })

  it('onPrevTurn/onNextTurn move currentIndex without changing the turn count', async () => {
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
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    renderProvider()
    expect(screen.getByTestId('current-index').textContent).toBe('1')

    act(() => { fireEvent.click(screen.getByTestId('prev')) })
    await waitFor(() => {
      expect(screen.getByTestId('current-index').textContent).toBe('0')
      expect(screen.getByTestId('turn-count').textContent).toBe('2')
    })
  })

  it('flags hasUnreadResponse when a turn settles while the user is viewing an older one', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: 'u1', role: 'user', content: 'First question', timestamp: new Date() },
        { id: 'a1', role: 'assistant', content: 'First answer', timestamp: new Date() },
        { id: 'u2', role: 'user', content: 'Second question', timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    const { rerender } = renderProvider()
    expect(screen.getByTestId('current-index').textContent).toBe('1')

    act(() => { fireEvent.click(screen.getByTestId('prev')) })
    await waitFor(() => expect(screen.getByTestId('current-index').textContent).toBe('0'))

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
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    rerender(<InlineChatProvider><Consumer /></InlineChatProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('has-unread').textContent).toBe('true')
      expect(screen.getByTestId('current-index').textContent).toBe('0')
    })
  })

  it('saves messages to sessionStorage keyed by userId when messages update', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    renderProvider()
    await waitFor(() => {
      expect(setItemSpy).toHaveBeenCalledWith(
        'rag_inline_chat_messages',
        expect.stringContaining('"userId":"user-1"')
      )
    })
    // sessionStorage, not localStorage
    expect(sessionStorage.getItem('rag_inline_chat_messages')).toContain('user-1')
    setItemSpy.mockRestore()
  })

  it('resets in-memory state when the logged-in user changes (no component remount required)', async () => {
    const { rerender } = renderProvider()

    vi.mocked(useSession).mockReturnValue({ data: { user: { id: 'user-2' } }, status: 'authenticated' } as any)
    rerender(<InlineChatProvider><Consumer /></InlineChatProvider>)

    await waitFor(() => {
      expect(mockClearMessages).toHaveBeenCalled()
    })
  })

  it('includes X-Pinned-Article-Ids header built from pinned articles', () => {
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1' }, { id: 'a2' }],
    } as any)
    let capturedHeaders: Record<string, string> | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedHeaders = opts.headers
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    expect(capturedHeaders?.['X-Pinned-Article-Ids']).toBe('a1,a2')
  })

  it('omits X-Pinned-Article-Ids header when no articles are pinned', () => {
    let capturedHeaders: Record<string, string> | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedHeaders = opts.headers
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    expect(capturedHeaders?.['X-Pinned-Article-Ids']).toBeUndefined()
  })

  it('shows toast.warning on 429 via onError callback', () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    capturedOnError?.(new Error('HTTP 429'))
    return import('sonner').then(({ toast }) => {
      expect(vi.mocked(toast.warning)).toHaveBeenCalledWith('已達每日問答上限')
    })
  })

  it('shows toast.error on 503 via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    capturedOnError?.(new Error('HTTP 503'))
    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('問答服務暫時無法使用，請稍後再試')
  })

  it('shows toast.error on a generic error via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    capturedOnError?.(new Error('Network error'))
    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('發生錯誤，請稍後再試')
  })

  it('calls refreshQuota when loading transitions from true to false', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    const { rerender } = renderProvider()

    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    rerender(<InlineChatProvider><Consumer /></InlineChatProvider>)

    await waitFor(() => {
      expect(mockRefreshQuota).toHaveBeenCalled()
    })
  })

  it('customAdapter maps {"thinking":"..."} SSE line to thinking_delta event', () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    renderProvider()
    const event = capturedAdapter.parse('data: {"thinking": "Reasoning about this"}')
    expect(event).toEqual({ type: 'thinking_delta', content: 'Reasoning about this' })
  })

  it('reports the error from useChat()', () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: new Error('HTTP 429'),
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    renderProvider()
    expect(screen.getByTestId('error').textContent).toBe('HTTP 429')
  })
})
