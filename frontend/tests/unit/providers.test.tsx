import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/lib/providers/session-provider', () => ({
  default: ({ children }: any) => <>{children}</>,
}))

vi.mock('@/lib/providers/i18n-provider', () => ({
  I18nProvider: ({ children }: any) => <>{children}</>,
  useI18n: vi.fn().mockReturnValue({ t: (k: string) => k, locale: 'en' }),
}))

vi.mock('@/lib/providers/topic-provider', () => ({
  TopicProvider: ({ children }: any) => <>{children}</>,
  useTopic: vi.fn().mockReturnValue({ selectedTopicId: null, topics: [] }),
}))

vi.mock('@/lib/providers/guest-mode-provider', () => ({
  GuestModeProvider: ({ children }: any) => <>{children}</>,
  useGuestMode: vi.fn().mockReturnValue({ isGuestMode: false }),
}))

vi.mock('@/lib/providers/tutorial-provider', () => ({
  TutorialProvider: ({ children }: any) => <>{children}</>,
  useTutorial: vi.fn().mockReturnValue({ isTutorialOpen: false, openTutorial: vi.fn() }),
}))

vi.mock('@/lib/providers/chat-quota-provider', () => ({
  ChatQuotaProvider: ({ children }: any) => <>{children}</>,
  useChatQuota: vi.fn().mockReturnValue({ quota: null, refreshQuota: vi.fn() }),
}))

vi.mock('@/lib/providers/theme-provider', () => ({
  ThemeProvider: ({ children }: any) => <>{children}</>,
  useTheme: vi.fn().mockReturnValue({ mode: 'auto', theme: 'light', cycleMode: vi.fn(), setMode: vi.fn() }),
}))

describe('AppProviders', () => {
  it('renders children inside all providers', async () => {
    const { AppProviders } = await import('@/lib/providers')
    render(
      <AppProviders>
        <div data-testid="child">Hello</div>
      </AppProviders>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('renders multiple children', async () => {
    const { AppProviders } = await import('@/lib/providers')
    render(
      <AppProviders>
        <span data-testid="a">A</span>
        <span data-testid="b">B</span>
      </AppProviders>
    )
    expect(screen.getByTestId('a')).toBeInTheDocument()
    expect(screen.getByTestId('b')).toBeInTheDocument()
  })
})

describe('providers re-exports', () => {
  it('exports useI18n hook', async () => {
    const { useI18n } = await import('@/lib/providers')
    expect(typeof useI18n).toBe('function')
  })

  it('exports useTopic hook', async () => {
    const { useTopic } = await import('@/lib/providers')
    expect(typeof useTopic).toBe('function')
  })

  it('exports useGuestMode hook', async () => {
    const { useGuestMode } = await import('@/lib/providers')
    expect(typeof useGuestMode).toBe('function')
  })

  it('exports useTutorial hook', async () => {
    const { useTutorial } = await import('@/lib/providers')
    expect(typeof useTutorial).toBe('function')
  })

  it('exports useTheme hook', async () => {
    const { useTheme } = await import('@/lib/providers')
    expect(typeof useTheme).toBe('function')
  })

  it('exports useChatQuota hook', async () => {
    const { useChatQuota } = await import('@/lib/providers')
    expect(typeof useChatQuota).toBe('function')
  })
})
