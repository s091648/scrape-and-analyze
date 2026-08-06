import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState, useCallback } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChat } from '@s091648/chatbot-plugin-ui'
import { useSession } from 'next-auth/react'
import { FloatChatProvider, useFloatChat } from '@/lib/providers/float-chat-provider'
import { usePinnedArticle } from '@/lib/providers/pinned-article-provider'

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

const { mockRefreshQuota, mockClearPinnedArticles } = vi.hoisted(() => ({
  mockRefreshQuota: vi.fn(),
  mockClearPinnedArticles: vi.fn(),
}))
vi.mock('@/lib/providers/chat-quota-provider', () => ({
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: mockRefreshQuota }),
}))

vi.mock('@/lib/providers/pinned-article-provider', () => ({
  usePinnedArticle: vi.fn().mockReturnValue({
    pinnedArticles: [],
    clearPinnedArticles: mockClearPinnedArticles,
  }),
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
  const {
    messages, messageSources, messageAttachments, isLoading, chatOpen,
    setChatOpen, onSend, onNewChat, onAbort,
  } = useFloatChat()
  return (
    <div>
      <span data-testid="message-count">{messages.length}</span>
      <span data-testid="chat-open">{String(chatOpen)}</span>
      <span data-testid="is-loading">{String(isLoading)}</span>
      <span data-testid="sources-for-2">{JSON.stringify(messageSources['2'] ?? [])}</span>
      <span data-testid="attachments-for-1">{JSON.stringify(messageAttachments['1'] ?? [])}</span>
      <button data-testid="send" onClick={() => onSend('hello')}>send</button>
      <button data-testid="send-blank" onClick={() => onSend('   ')}>send-blank</button>
      <button data-testid="new-chat" onClick={onNewChat}>new-chat</button>
      <button data-testid="abort" onClick={onAbort}>abort</button>
      <button data-testid="open" onClick={() => setChatOpen(true)}>open</button>
    </div>
  )
}

function renderProvider() {
  return render(
    <FloatChatProvider>
      <Consumer />
    </FloatChatProvider>
  )
}

describe('FloatChatProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSession).mockReturnValue({ data: { user: { id: 'user-1' } }, status: 'authenticated' } as any)
    vi.mocked(usePinnedArticle).mockReturnValue({
      pinnedArticles: [],
      clearPinnedArticles: mockClearPinnedArticles,
    } as any)
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
  })

  it('exposes messages and isLoading from the underlying useChat session', async () => {
    vi.mocked(useChat).mockReturnValue({
      messages: [
        { id: '1', role: 'user', content: 'hi', timestamp: new Date() },
        { id: '2', role: 'assistant', content: 'hello', timestamp: new Date() },
      ],
      sendMessage: mockSendMessage,
      isLoading: true,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    await renderProvider()
    expect(screen.getByTestId('message-count').textContent).toBe('2')
    expect(screen.getByTestId('is-loading').textContent).toBe('true')
  })

  it('onSend forwards trimmed text to sendMessage', async () => {
    await renderProvider()
    fireEvent.click(screen.getByTestId('send'))
    expect(mockSendMessage).toHaveBeenCalledWith('hello')
  })

  it('onSend does not call sendMessage for blank text', async () => {
    await renderProvider()
    fireEvent.click(screen.getByTestId('send-blank'))
    expect(mockSendMessage).not.toHaveBeenCalled()
  })

  it('onAbort delegates to useChat().abort', async () => {
    await renderProvider()
    fireEvent.click(screen.getByTestId('abort'))
    expect(mockAbort).toHaveBeenCalled()
  })

  it('setChatOpen updates chatOpen', async () => {
    await renderProvider()
    expect(screen.getByTestId('chat-open').textContent).toBe('false')
    fireEvent.click(screen.getByTestId('open'))
    expect(screen.getByTestId('chat-open').textContent).toBe('true')
  })

  it('onNewChat clears messages, pinned articles, and localStorage', async () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')
    await renderProvider()
    fireEvent.click(screen.getByTestId('new-chat'))
    expect(mockClearMessages).toHaveBeenCalled()
    expect(mockClearPinnedArticles).toHaveBeenCalled()
    expect(removeItemSpy).toHaveBeenCalledWith('rag_float_chat_messages')
    removeItemSpy.mockRestore()
  })

  // Regression: every other test in this file mocks useChat() to return static values, so
  // clearMessages is a bare vi.fn() that can't expose the real bug — the actual library's
  // clearMessages() resets `messages` to whatever `initialMessages` equals on the render that
  // *created* that clearMessages closure. This fake reproduces that one behavior (not the rest
  // of useChat) so the test can catch onNewChat regressing back into a no-op when history exists.
  it('onNewChat actually empties messages when there is existing history (pencil-icon no-op regression)', async () => {
    localStorage.setItem('rag_float_chat_messages', JSON.stringify({
      userId: 'user-1',
      messages: [{ id: '1', role: 'user', content: 'old question', timestamp: new Date().toISOString() }],
    }))

    vi.mocked(useChat).mockImplementation((opts: any) => {
      const [msgs, setMsgs] = useState(opts.initialMessages)
      const clear = useCallback(() => setMsgs(opts.initialMessages), [opts.initialMessages])
      return { messages: msgs, sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: clear, abort: mockAbort }
    })

    renderProvider()
    await waitFor(() => {
      expect(screen.getByTestId('message-count').textContent).toBe('1')
    })

    fireEvent.click(screen.getByTestId('new-chat'))

    await waitFor(() => {
      expect(screen.getByTestId('message-count').textContent).toBe('0')
    })
  })

  it('saves messages to localStorage keyed by userId when messages update', async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    await renderProvider()
    await waitFor(() => {
      expect(setItemSpy).toHaveBeenCalledWith(
        'rag_float_chat_messages',
        expect.stringContaining('"userId":"user-1"')
      )
    })
    setItemSpy.mockRestore()
  })

  it('clears localStorage when the session becomes unauthenticated', async () => {
    vi.mocked(useSession).mockReturnValue({ data: null, status: 'unauthenticated' } as any)
    const removeItemSpy = vi.spyOn(Storage.prototype, 'removeItem')
    await renderProvider()
    await waitFor(() => {
      expect(removeItemSpy).toHaveBeenCalledWith('rag_float_chat_messages')
    })
    removeItemSpy.mockRestore()
  })

  it('resets in-memory state when the logged-in user changes (no component remount required)', async () => {
    const { rerender } = renderProvider()

    vi.mocked(useSession).mockReturnValue({ data: { user: { id: 'user-2' } }, status: 'authenticated' } as any)
    rerender(
      <FloatChatProvider>
        <Consumer />
      </FloatChatProvider>
    )

    await waitFor(() => {
      expect(mockClearMessages).toHaveBeenCalled()
    })
  })

  it('shows toast warning and refreshes quota on 429 error', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    await renderProvider()
    capturedOnError?.(new Error('HTTP 429'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.warning)).toHaveBeenCalledWith('已達每日問答上限')
    expect(mockRefreshQuota).toHaveBeenCalled()
  })

  it('shows toast.error on 503 via onError callback', async () => {
    let capturedOnError: ((e: Error) => void) | undefined
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedOnError = opts.onError
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    await renderProvider()
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
    await renderProvider()
    capturedOnError?.(new Error('unexpected failure'))

    const { toast } = await import('sonner')
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith('發生錯誤，請稍後再試')
  })

  it('customAdapter maps {"thinking":"..."} SSE line to thinking_delta event', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    await renderProvider()

    const event = capturedAdapter.parse('data: {"thinking": "Let me reason through this"}')
    expect(event).toEqual({ type: 'thinking_delta', content: 'Let me reason through this' })
  })

  it('customAdapter returns null for a {"sources":[...]} SSE line (handled via side-effect)', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return { messages: [], sendMessage: mockSendMessage, isLoading: false, error: null, clearMessages: mockClearMessages, abort: mockAbort }
    })
    await renderProvider()

    const line = 'data: {"sources": [{"id":"s1","title":"Paper","url":"https://example.com","public_article_id":null}]}'
    expect(capturedAdapter.parse(line)).toBeNull()
  })

  it('captures pending sources onto the last assistant message once loading settles', async () => {
    let capturedAdapter: any
    vi.mocked(useChat).mockImplementation((opts: any) => {
      capturedAdapter = opts.streamAdapter
      return {
        messages: [{ id: '2', role: 'assistant', content: 'answer', timestamp: new Date() }],
        sendMessage: mockSendMessage,
        isLoading: true,
        error: null,
        clearMessages: mockClearMessages,
        abort: mockAbort,
      }
    })
    const { rerender } = renderProvider()

    // Sources SSE line arrives mid-stream — captured via the adapter's side-effect ref.
    capturedAdapter.parse('data: {"sources": [{"id":"s1","title":"Paper","url":"https://example.com","public_article_id":null}]}')

    // Stream settles (isLoading flips true → false) — sources get attached to the assistant message.
    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '2', role: 'assistant', content: 'answer', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    rerender(<FloatChatProvider><Consumer /></FloatChatProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('sources-for-2').textContent).toContain('"id":"s1"')
    })
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
    rerender(<FloatChatProvider><Consumer /></FloatChatProvider>)

    await waitFor(() => {
      expect(mockRefreshQuota).toHaveBeenCalled()
    })
  })

  it('opens the panel automatically when a pinned article is added', async () => {
    vi.mocked(usePinnedArticle).mockReturnValue({
      pinnedArticles: [],
      clearPinnedArticles: mockClearPinnedArticles,
    } as any)
    const { rerender } = renderProvider()
    expect(screen.getByTestId('chat-open').textContent).toBe('false')

    vi.mocked(usePinnedArticle).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }],
      clearPinnedArticles: mockClearPinnedArticles,
    } as any)
    rerender(<FloatChatProvider><Consumer /></FloatChatProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('chat-open').textContent).toBe('true')
    })
  })

  it('attaches the pinned-articles snapshot to a newly sent user message', async () => {
    vi.mocked(usePinnedArticle).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }],
      clearPinnedArticles: mockClearPinnedArticles,
    } as any)
    const { rerender } = renderProvider()
    fireEvent.click(screen.getByTestId('send'))

    vi.mocked(useChat).mockReturnValue({
      messages: [{ id: '1', role: 'user', content: 'hello', timestamp: new Date() }],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: mockClearMessages,
      abort: mockAbort,
    } as any)
    rerender(<FloatChatProvider><Consumer /></FloatChatProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('attachments-for-1').textContent).toContain('Paper One')
    })
  })
})
