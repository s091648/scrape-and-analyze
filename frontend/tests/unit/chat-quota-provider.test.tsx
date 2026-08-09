import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'

vi.mock('@/lib/providers/auth-token-provider', () => ({
  useAuthToken: vi.fn(),
}))

import { useAuthToken } from '@/lib/providers/auth-token-provider'
import { setCurrentToken } from '@/lib/auth-token-store'

const mockFetch = vi.fn()
global.fetch = mockFetch

// apiFetch() awaits the real (unmocked) auth-token-store's waitForToken() internally,
// independent of ChatQuotaProvider's own useAuthToken()-based gating — keep both in
// sync so a mocked "ready" state here doesn't leave apiFetch hanging on the real store.
function makeAuthTokenMock(token: string | undefined, isLoading = false) {
  setCurrentToken(token, isLoading)
  return { token, isLoading }
}

function makeQuotaResponse(overrides = {}) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ tier: 'guest', remaining: 5, limit: 10, ...overrides }),
  }
}

describe('ChatQuotaProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue(makeQuotaResponse())
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock('guest-token'))
  })

  it('renders children', async () => {
    const { ChatQuotaProvider } = await import('@/lib/providers/chat-quota-provider')
    render(
      <ChatQuotaProvider>
        <span data-testid="child">hello</span>
      </ChatQuotaProvider>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('fetches quota via apiFetch once a token is available', async () => {
    const { ChatQuotaProvider } = await import('@/lib/providers/chat-quota-provider')
    render(<ChatQuotaProvider><div /></ChatQuotaProvider>)
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/proxy/chat/quota'),
        expect.any(Object),
      )
    })
  })

  it('does not fetch while the token is still loading', async () => {
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock(undefined, true))
    const { ChatQuotaProvider } = await import('@/lib/providers/chat-quota-provider')
    render(<ChatQuotaProvider><div /></ChatQuotaProvider>)
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('does not fetch when there is no token at all', async () => {
    vi.mocked(useAuthToken).mockReturnValue(makeAuthTokenMock(undefined, false))
    const { ChatQuotaProvider } = await import('@/lib/providers/chat-quota-provider')
    render(<ChatQuotaProvider><div /></ChatQuotaProvider>)
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('exposes quota value to consumers after fetch', async () => {
    mockFetch.mockResolvedValue(makeQuotaResponse({ remaining: 7, limit: 10, tier: 'user' }))

    const { ChatQuotaProvider, useChatQuota } = await import('@/lib/providers/chat-quota-provider')
    function Consumer() {
      const { quota } = useChatQuota()
      if (!quota) return <span data-testid="no-quota" />
      return <span data-testid="quota">{quota.remaining}/{quota.limit}</span>
    }

    render(<ChatQuotaProvider><Consumer /></ChatQuotaProvider>)
    await waitFor(() => {
      expect(screen.getByTestId('quota')).toHaveTextContent('7/10')
    })
  })

  it('quota remains null when fetch returns non-ok response', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) })

    const { ChatQuotaProvider, useChatQuota } = await import('@/lib/providers/chat-quota-provider')
    function Consumer() {
      const { quota } = useChatQuota()
      return <span data-testid="result">{quota === null ? 'null' : 'has-quota'}</span>
    }

    render(<ChatQuotaProvider><Consumer /></ChatQuotaProvider>)
    await waitFor(() => {
      expect(screen.getByTestId('result')).toHaveTextContent('null')
    })
  })

  it('quota remains null when fetch throws', async () => {
    mockFetch.mockRejectedValue(new Error('network error'))

    const { ChatQuotaProvider, useChatQuota } = await import('@/lib/providers/chat-quota-provider')
    function Consumer() {
      const { quota } = useChatQuota()
      return <span data-testid="result">{quota === null ? 'null' : 'has-quota'}</span>
    }

    render(<ChatQuotaProvider><Consumer /></ChatQuotaProvider>)
    await waitFor(() => {
      expect(screen.getByTestId('result')).toHaveTextContent('null')
    })
  })

  it('refreshQuota re-fetches and updates quota', async () => {
    mockFetch
      .mockResolvedValueOnce(makeQuotaResponse({ remaining: 5 }))
      .mockResolvedValueOnce(makeQuotaResponse({ remaining: 4 }))

    const { ChatQuotaProvider, useChatQuota } = await import('@/lib/providers/chat-quota-provider')
    function Consumer() {
      const { quota, refreshQuota } = useChatQuota()
      return (
        <div>
          <span data-testid="remaining">{quota?.remaining ?? 'null'}</span>
          <button data-testid="refresh" onClick={() => refreshQuota()} />
        </div>
      )
    }

    render(<ChatQuotaProvider><Consumer /></ChatQuotaProvider>)
    await waitFor(() => expect(screen.getByTestId('remaining')).toHaveTextContent('5'))

    await act(async () => {
      screen.getByTestId('refresh').click()
    })

    await waitFor(() => expect(screen.getByTestId('remaining')).toHaveTextContent('4'))
  })
})
