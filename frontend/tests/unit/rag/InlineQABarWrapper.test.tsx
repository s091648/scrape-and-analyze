import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useChat, AgentInput } from '@Teng91/chatbot-plugin-ui'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn().mockReturnValue({ data: null, status: 'unauthenticated' }),
}))

vi.mock('@/lib/providers', () => ({
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null }),
}))

vi.mock('@/lib/chat-session', () => ({
  loadSession: vi.fn().mockReturnValue([]),
  saveSession: vi.fn(),
  clearSession: vi.fn(),
}))

const mockSendMessage = vi.fn()
const mockMessages = [
  { id: '1', role: 'user', content: 'hello', timestamp: new Date() },
  { id: '2', role: 'assistant', content: 'Hi there!', timestamp: new Date() },
]

vi.mock('@Teng91/chatbot-plugin-ui', () => ({
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
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useChat).mockReturnValue({
      messages: [],
      sendMessage: mockSendMessage,
      isLoading: false,
      error: null,
      clearMessages: vi.fn(),
    })
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
      '@/components/features/rag/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    expect(screen.getByTestId('agent-input')).toBeInTheDocument()
  })

  it('calls sendMessage when send button clicked with non-empty text', async () => {
    const { InlineQABarWrapper } = await import(
      '@/components/features/rag/InlineQABarWrapper'
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
      '@/components/features/rag/InlineQABarWrapper'
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
      '@/components/features/rag/InlineQABarWrapper'
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
      '@/components/features/rag/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    const cursor = document.querySelector('.animate-pulse')
    expect(cursor).toBeInTheDocument()
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
      '@/components/features/rag/InlineQABarWrapper'
    )
    render(<InlineQABarWrapper />)
    expect(screen.getByText('已達每日問答上限')).toBeInTheDocument()
  })
})
