import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('next-auth/react', () => ({
  useSession: vi.fn(),
}))

import { useSession } from 'next-auth/react'

const mockFetch = vi.fn()
global.fetch = mockFetch

const STORAGE_KEY = 'guest_token_pair'

function makeSessionMock(status: 'authenticated' | 'unauthenticated' | 'loading', accessToken?: string) {
  return {
    data: status === 'authenticated' ? { accessToken: accessToken ?? 'real-user-token' } : null,
    status,
    update: vi.fn(),
  }
}

function guestIssueResponse(overrides: Partial<{ access_token: string; refresh_token: string; expires_in: number }> = {}) {
  return {
    ok: true,
    json: async () => ({
      access_token: 'guest-access-1',
      refresh_token: 'guest-refresh-1',
      expires_in: 3600,
      ...overrides,
    }),
  }
}

describe('AuthTokenProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    mockFetch.mockResolvedValue(guestIssueResponse())
    vi.mocked(useSession).mockReturnValue(makeSessionMock('unauthenticated') as any)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders children', async () => {
    const { AuthTokenProvider } = await import('@/lib/providers/auth-token-provider')
    render(
      <AuthTokenProvider>
        <span data-testid="child">hello</span>
      </AuthTokenProvider>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })

  it('acquires a guest token when unauthenticated and no cached pair exists', async () => {
    const { AuthTokenProvider } = await import('@/lib/providers/auth-token-provider')
    render(<AuthTokenProvider><div /></AuthTokenProvider>)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/proxy/auth/guest', { method: 'POST' })
    })
  })

  it('exposes the acquired guest token to consumers', async () => {
    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token, isLoading } = useAuthToken()
      return <span data-testid="token">{isLoading ? 'loading' : token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('guest-access-1')
    })
  })

  it('reuses a cached, still-valid guest token instead of issuing a new one', async () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      accessToken: 'cached-access',
      refreshToken: 'cached-refresh',
      expiresAt: Date.now() + 60 * 60 * 1000,
    }))

    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token } = useAuthToken()
      return <span data-testid="token">{token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('cached-access')
    })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('does not acquire a guest token when a real session exists', async () => {
    vi.mocked(useSession).mockReturnValue(makeSessionMock('authenticated', 'real-user-token') as any)

    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token } = useAuthToken()
      return <span data-testid="token">{token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('real-user-token')
    })
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('does not fetch while session status is loading', async () => {
    vi.mocked(useSession).mockReturnValue(makeSessionMock('loading') as any)
    const { AuthTokenProvider } = await import('@/lib/providers/auth-token-provider')
    render(<AuthTokenProvider><div /></AuthTokenProvider>)
    await new Promise(r => setTimeout(r, 50))
    expect(mockFetch).not.toHaveBeenCalled()
  })

  it('exchanges a stale cached access token for a fresh one via refresh, keeping the same refresh token', async () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      accessToken: 'stale-access',
      refreshToken: 'still-valid-refresh',
      expiresAt: Date.now() - 1000, // already past the refresh margin
    }))
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'refreshed-access', expires_in: 3600 }),
    })

    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token } = useAuthToken()
      return <span data-testid="token">{token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/proxy/auth/guest/refresh',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ refresh_token: 'still-valid-refresh' }),
        }),
      )
    })
    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('refreshed-access')
    })
  })

  it('falls back to issuing a brand-new pair when refresh fails', async () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      accessToken: 'stale-access',
      refreshToken: 'expired-refresh',
      expiresAt: Date.now() - 1000,
    }))
    mockFetch
      .mockResolvedValueOnce({ ok: false, json: async () => ({}) }) // refresh fails
      .mockResolvedValueOnce(guestIssueResponse({ access_token: 'brand-new-access' })) // fresh pair

    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token } = useAuthToken()
      return <span data-testid="token">{token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('brand-new-access')
    })
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/auth/guest/refresh', expect.any(Object))
    expect(mockFetch).toHaveBeenCalledWith('/api/proxy/auth/guest', { method: 'POST' })
  })

  it('clears the cached guest pair once the user logs in', async () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      accessToken: 'guest-access',
      refreshToken: 'guest-refresh',
      expiresAt: Date.now() + 60 * 60 * 1000,
    }))
    vi.mocked(useSession).mockReturnValue(makeSessionMock('authenticated', 'real-user-token') as any)

    const { AuthTokenProvider, useAuthToken } = await import('@/lib/providers/auth-token-provider')
    function Consumer() {
      const { token } = useAuthToken()
      return <span data-testid="token">{token ?? 'none'}</span>
    }
    render(<AuthTokenProvider><Consumer /></AuthTokenProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('token')).toHaveTextContent('real-user-token')
    })
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
