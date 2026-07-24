import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { ReactNode } from 'react'
import { TopicProvider, useTopic } from '@/lib/providers/topic-provider'

const { mockFetchTopics } = vi.hoisted(() => ({ mockFetchTopics: vi.fn() }))
vi.mock('@/lib/api/topics', () => ({ fetchTopics: mockFetchTopics }))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
}))

// 018-public-api-auth: TopicProvider now waits for a resolved auth token
// (real session or guest) before calling /topics.
vi.mock('@/lib/providers/auth-token-provider', () => ({
  useAuthToken: vi.fn(),
}))

import { useAuthToken } from '@/lib/providers/auth-token-provider'

function makeAuthTokenMock(token: string | undefined, isLoading = false) {
  return { token, isLoading }
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock('test-token'))
})

const sampleTopics = [
  { id: 't1', name: 'ai', display_name: 'AI', color_hex: '#3b82f6', sort_order: 0, tag_mode: 'unsupervised' },
  { id: 't2', name: 'ml', display_name: 'ML', color_hex: null, sort_order: 1, tag_mode: 'unsupervised' },
]

function TestConsumer() {
  const { topics, selectedTopicId, selectedTopic, isLoading, setSelectedTopicId, refresh } = useTopic()
  return (
    <div>
      <span data-testid="selected">{selectedTopicId ?? 'none'}</span>
      <span data-testid="topic-name">{selectedTopic?.display_name ?? 'none'}</span>
      <span data-testid="loading">{isLoading ? 'loading' : 'ready'}</span>
      <span data-testid="count">{topics.length}</span>
      <button onClick={() => setSelectedTopicId('t2')}>select-t2</button>
      <button onClick={() => void refresh()}>refresh</button>
    </div>
  )
}

function renderProvider(children?: ReactNode) {
  return render(<TopicProvider>{children ?? <TestConsumer />}</TopicProvider>)
}

describe('TopicProvider', () => {
  it('starts in loading state then resolves to ready', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
  })

  it('loads topics from API and exposes them', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('2'))
  })

  it('selects the first topic by default when localStorage is empty', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('t1'))
  })

  it('restores selectedTopicId from localStorage when valid', async () => {
    localStorage.setItem('selectedTopicId', 't2')
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('t2'))
  })

  it('falls back to first topic when stored id no longer exists', async () => {
    localStorage.setItem('selectedTopicId', 'stale-id')
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('t1'))
  })

  it('selectedTopic matches the selectedTopicId object', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('topic-name').textContent).toBe('AI'))
  })

  it('setSelectedTopicId updates state and writes to localStorage', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    fireEvent.click(screen.getByText('select-t2'))
    await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('t2'))
    expect(localStorage.getItem('selectedTopicId')).toBe('t2')
  })

  it('refresh calls fetchTopics a second time', async () => {
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    fireEvent.click(screen.getByText('refresh'))
    await waitFor(() => expect(mockFetchTopics).toHaveBeenCalledTimes(2))
  })

  it('handles empty topics list — selectedTopicId is null', async () => {
    mockFetchTopics.mockResolvedValue([])
    renderProvider()
    await waitFor(() => expect(screen.getByTestId('loading').textContent).toBe('ready'))
    expect(screen.getByTestId('selected').textContent).toBe('none')
    expect(screen.getByTestId('count').textContent).toBe('0')
  })

  it('does not fetch topics while the auth token is still loading', async () => {
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock(undefined, true))
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchTopics).not.toHaveBeenCalled()
  })

  it('does not fetch topics when there is no token at all', async () => {
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock(undefined, false))
    mockFetchTopics.mockResolvedValue(sampleTopics)
    renderProvider()
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetchTopics).not.toHaveBeenCalled()
  })

  it('fetches topics once the auth token resolves', async () => {
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock(undefined, true))
    mockFetchTopics.mockResolvedValue(sampleTopics)
    const { rerender } = renderProvider()
    await new Promise(r => setTimeout(r, 20))
    expect(mockFetchTopics).not.toHaveBeenCalled()

    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock('guest-token', false))
    rerender(<TopicProvider><TestConsumer /></TopicProvider>)
    await waitFor(() => expect(mockFetchTopics).toHaveBeenCalledTimes(1))
  })
})
