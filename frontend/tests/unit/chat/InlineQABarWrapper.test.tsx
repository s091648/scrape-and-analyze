import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AgentInput } from '@s091648/chatbot-plugin-ui'

// InlineQABarWrapper is now a thin presentational consumer of useInlineChat() (see
// lib/providers/inline-chat-provider.tsx) — the actual useChat()/sessionStorage/adapter/toast/
// turns-pagination logic that used to live here is now covered by
// tests/unit/providers/inline-chat-provider.test.tsx. This file only covers what the wrapper
// itself still owns: the pin-articles UI, the Escape-to-abort shortcut (deliberately kept
// component-scoped rather than provider-scoped — see InlineQABarWrapper.tsx), and forwarding
// the context's conversation state to onConversationChange/onMessageSent.

const zhTW: Record<string, string> = {
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
const mockToggleGroupArticle = vi.fn()
const mockRemoveGroup = vi.fn()
const mockOnSend = vi.fn()
const mockOnAbort = vi.fn()
const mockOnPrevTurn = vi.fn()
const mockOnNextTurn = vi.fn()

function defaultInlineChat() {
  return {
    messages: [],
    turns: [],
    currentTurnIndex: 0,
    isLoading: false,
    error: null,
    hasUnreadResponse: false,
    onPrevTurn: mockOnPrevTurn,
    onNextTurn: mockOnNextTurn,
    onSend: mockOnSend,
    onAbort: mockOnAbort,
  }
}

vi.mock('@/lib/providers', () => ({
  useI18n: vi.fn().mockReturnValue({
    t: (k: string, params?: Record<string, any>) => {
      if (k === 'rag.weeklyGroupPill') return `${params?.date} · ${params?.count} articles`
      return zhTW[k] ?? k
    },
  }),
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: mockCycleMode, setMode: vi.fn() }),
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
  usePinnedReport: vi.fn().mockReturnValue({
    pinnedArticles: [],
    removePinnedArticle: mockRemovePinnedArticle,
    pinnedGroups: [],
    toggleGroupArticle: mockToggleGroupArticle,
    removeGroup: mockRemoveGroup,
    isPinned: (_id: string) => false,
  }),
  useInlineChat: vi.fn(),
}))

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
}))

describe('InlineQABarWrapper', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { useInlineChat, usePinnedReport } = await import('@/lib/providers')
    vi.mocked(useInlineChat).mockReturnValue(defaultInlineChat() as any)
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
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.getByTestId('agent-input')).toBeInTheDocument()
  })

  // Regression: AgentInput renders every role:'tool' message it's given as an always-expanded,
  // uncollapsible card (raw JSON args + full result, no truncation of its own) in its own small
  // toolCallsArea — which used to blow out the input bar's height, crowding out the report/chat
  // panels below it, whether from one huge tool result or many accumulated across persisted
  // history. Tool-call activity now renders properly inside AnswerDisplay instead (see
  // ToolCallBlock in AnswerDisplay.tsx), so AgentInput should never see a role:'tool' message —
  // no scoping or truncation needed at this layer at all anymore.
  it('never passes role:tool messages to AgentInput', async () => {
    const hugeResult = 'x'.repeat(5000)
    const { useInlineChat } = await import('@/lib/providers')
    vi.mocked(useInlineChat).mockReturnValue({
      ...defaultInlineChat(),
      messages: [
        { id: 'u1', role: 'user', content: 'question' },
        { id: 'a1', role: 'assistant', content: 'answer' },
        {
          id: 't1',
          role: 'tool',
          content: '',
          toolCall: { id: 'c1', name: 'search_articles', arguments: { query: 'x' } },
          toolResult: { toolCallId: 'c1', content: hugeResult, isError: false },
        },
      ],
    } as any)

    let receivedMessages: any[] | undefined
    vi.mocked(AgentInput).mockImplementationOnce(({ messages, onSend }: any) => {
      receivedMessages = messages
      return <button data-testid="send-btn" onClick={() => onSend('x')}>Send</button>
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)

    expect(receivedMessages?.some((m: any) => m.role === 'tool')).toBe(false)
    expect(receivedMessages?.map((m: any) => m.id)).toEqual(['u1', 'a1'])
  })

  it('delegates send button clicks to the context onSend', async () => {
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(mockOnSend).toHaveBeenCalledWith('test question')
  })

  it('does not call onSend when text is blank', async () => {
    vi.mocked(AgentInput).mockImplementationOnce(({ onSend }: any) => (
      <button data-testid="blank-send" onClick={() => onSend('   ')}>Blank</button>
    ))

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.click(screen.getByTestId('blank-send'))
    expect(mockOnSend).not.toHaveBeenCalled()
  })

  it('calls onMessageSent when a message is sent', async () => {
    const onMessageSent = vi.fn()
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper onMessageSent={onMessageSent} />)
    fireEvent.click(screen.getByTestId('send-btn'))
    expect(onMessageSent).toHaveBeenCalled()
  })

  it('does not throw when onMessageSent is omitted', async () => {
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(() => fireEvent.click(screen.getByTestId('send-btn'))).not.toThrow()
  })

  it('forwards the context conversation snapshot via onConversationChange', async () => {
    const { useInlineChat } = await import('@/lib/providers')
    vi.mocked(useInlineChat).mockReturnValue({
      ...defaultInlineChat(),
      turns: [{ userMessage: { id: 'u1', role: 'user', content: 'hi' }, assistantMessage: { id: 'a1', role: 'assistant', content: 'hello' }, sources: [] }],
      currentTurnIndex: 0,
      isLoading: true,
      hasUnreadResponse: true,
    } as any)
    const onConversationChange = vi.fn()

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper onConversationChange={onConversationChange} />)

    const snapshot = onConversationChange.mock.calls.at(-1)?.[0]
    expect(snapshot?.turns).toHaveLength(1)
    expect(snapshot?.currentIndex).toBe(0)
    expect(snapshot?.isLoading).toBe(true)
    expect(snapshot?.hasUnreadResponse).toBe(true)
    expect(snapshot?.onPrevTurn).toBe(mockOnPrevTurn)
    expect(snapshot?.onNextTurn).toBe(mockOnNextTurn)
  })

  it('passes mode from useTheme as theme prop to AgentInput', async () => {
    const { useTheme } = await import('@/lib/providers')
    vi.mocked(useTheme).mockReturnValue({ mode: 'dark', theme: 'dark', cycleMode: mockCycleMode, setMode: vi.fn() } as any)

    let receivedTheme: string | undefined
    vi.mocked(AgentInput).mockImplementationOnce(({ theme, onSend }: any) => {
      receivedTheme = theme
      return <button data-testid="send-btn" onClick={() => onSend('x')}>Send</button>
    })

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(receivedTheme).toBe('dark')
  })

  it('shows quota text when quota has remaining >= 0', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValue({ quota: { remaining: 5, limit: 10 }, refreshQuota: vi.fn() } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.getByText(/5 \/ 10/)).toBeInTheDocument()
    expect(screen.getByText(/rag\.remainingRequests/)).toBeInTheDocument()
  })

  it('does not show quota text when quota is null', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    vi.mocked(useChatQuota).mockReturnValue({ quota: null, refreshQuota: vi.fn() } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    expect(screen.queryByText(/\/ 10/)).not.toBeInTheDocument()
  })

  it('calls abort when Escape pressed while loading', async () => {
    const { useInlineChat } = await import('@/lib/providers')
    vi.mocked(useInlineChat).mockReturnValue({ ...defaultInlineChat(), isLoading: true } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(mockOnAbort).toHaveBeenCalled()
  })

  it('does not call abort on non-Escape key while loading', async () => {
    const { useInlineChat } = await import('@/lib/providers')
    vi.mocked(useInlineChat).mockReturnValue({ ...defaultInlineChat(), isLoading: true } as any)

    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.keyDown(window, { key: 'Enter' })
    expect(mockOnAbort).not.toHaveBeenCalled()
  })

  it('does not call abort on Escape while not loading', async () => {
    const { InlineQABarWrapper } = await import('@/components/features/chat/InlineQABarWrapper')
    render(<InlineQABarWrapper />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(mockOnAbort).not.toHaveBeenCalled()
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
  })

  // ── Pinning (2026-07-12, US7: pin weekly report into chat) ──────────────

  it('renders a chip for each pinned article and removes it on click', async () => {
    const { usePinnedReport } = await import('@/lib/providers')
    vi.mocked(usePinnedReport).mockReturnValue({
      pinnedArticles: [{ id: 'a1', title: 'Paper One' }],
      removePinnedArticle: mockRemovePinnedArticle,
      pinnedGroups: [],
      toggleGroupArticle: mockToggleGroupArticle,
      removeGroup: mockRemoveGroup,
      isPinned: (_id: string) => false,
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
})
