import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

const mockUseSession = vi.fn()
const mockUseGuestMode = vi.fn()

vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
  signOut: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({ get: vi.fn(() => null) }),
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
  useGuestMode: () => mockUseGuestMode(),
}))

vi.mock('@/lib/api/auth', () => ({
  fetchMe: vi.fn().mockResolvedValue(null),
  updateMe: vi.fn(),
  changePassword: vi.fn(),
  deleteMe: vi.fn(),
  unlinkGoogle: vi.fn(),
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
}))

vi.mock('@/components/ui/skeleton', () => ({
  Skeleton: () => <div data-testid="skeleton" />,
}))

vi.mock('next/link', () => ({
  default: ({ children, href }: any) => <a href={href}>{children}</a>,
}))

describe('SettingsPageContent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseSession.mockReturnValue({ data: null })
    mockUseGuestMode.mockReturnValue({ isGuestMode: false })
  })

  it('renders guest restriction view when in guest mode', async () => {
    mockUseGuestMode.mockReturnValue({ isGuestMode: true })
    const { default: SettingsPageContent } = await import('@/app/settings/settings-page-content')
    render(<SettingsPageContent />)
    expect(screen.getByText('guest.restrictedTitle')).toBeInTheDocument()
    expect(screen.getByText('guest.restrictedMessage')).toBeInTheDocument()
  })

  it('does not crash on re-render when in guest mode (hooks violation check)', async () => {
    mockUseGuestMode.mockReturnValue({ isGuestMode: true })
    const { default: SettingsPageContent } = await import('@/app/settings/settings-page-content')
    const { rerender } = render(<SettingsPageContent />)
    rerender(<SettingsPageContent />)
    expect(screen.getByText('guest.restrictedTitle')).toBeInTheDocument()
  })

  it('renders settings skeleton while loading when not in guest mode', async () => {
    mockUseGuestMode.mockReturnValue({ isGuestMode: false })
    mockUseSession.mockReturnValue({ data: { accessToken: 'tok' } })
    const { default: SettingsPageContent } = await import('@/app/settings/settings-page-content')
    render(<SettingsPageContent />)
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  })
})
