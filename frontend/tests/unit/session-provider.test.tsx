import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import { SessionProvider } from 'next-auth/react'
import SessionProviderWrapper from '@/lib/providers/session-provider'

vi.mock('next-auth/react', () => ({
  SessionProvider: vi.fn(({ children }: { children: React.ReactNode }) => <>{children}</>),
}))

describe('SessionProviderWrapper', () => {
  it('renders children through next-auth SessionProvider with polling enabled', () => {
    render(
      <SessionProviderWrapper>
        <div data-testid="child">hi</div>
      </SessionProviderWrapper>,
    )

    const props = vi.mocked(SessionProvider).mock.calls[0][0]
    expect(props.refetchOnWindowFocus).toBe(false)
    // Access tokens are 1h-lived (see the component's own comment) — polled well ahead of
    // expiry independent of the reactive apiFetch() 401 refresh path.
    expect(props.refetchInterval).toBe(5 * 60)
  })
})
