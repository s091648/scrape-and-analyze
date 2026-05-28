import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string, params?: Record<string, any>) => {
      const map: Record<string, string> = {
        'tags.pendingChanges': `${params?.count ?? 0} pending changes`,
        'tags.discardMoves': 'Discard',
        'tags.confirmMoves': 'Confirm',
      }
      return map[key] ?? key
    },
  }),
}))

describe('PendingChangesPanel', () => {
  const defaultProps = {
    count: 3,
    confirming: false,
    onConfirm: vi.fn(),
    onDiscard: vi.fn(),
  }

  it('renders pending change count', async () => {
    const { PendingChangesPanel } = await import('@/components/features/tags/pending-changes-panel')
    render(<PendingChangesPanel {...defaultProps} />)
    expect(screen.getByText('3 pending changes')).toBeInTheDocument()
  })

  it('renders confirm and discard buttons', async () => {
    const { PendingChangesPanel } = await import('@/components/features/tags/pending-changes-panel')
    render(<PendingChangesPanel {...defaultProps} />)
    expect(screen.getByText('Discard')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
  })

  it('calls onConfirm when confirm button clicked', async () => {
    const onConfirm = vi.fn()
    const { PendingChangesPanel } = await import('@/components/features/tags/pending-changes-panel')
    render(<PendingChangesPanel {...defaultProps} onConfirm={onConfirm} />)
    fireEvent.click(screen.getByText('Confirm'))
    expect(onConfirm).toHaveBeenCalled()
  })

  it('calls onDiscard when discard button clicked', async () => {
    const onDiscard = vi.fn()
    const { PendingChangesPanel } = await import('@/components/features/tags/pending-changes-panel')
    render(<PendingChangesPanel {...defaultProps} onDiscard={onDiscard} />)
    fireEvent.click(screen.getByText('Discard'))
    expect(onDiscard).toHaveBeenCalled()
  })

  it('disables buttons when confirming is true', async () => {
    const { PendingChangesPanel } = await import('@/components/features/tags/pending-changes-panel')
    render(<PendingChangesPanel {...defaultProps} confirming={true} />)
    const buttons = screen.getAllByRole('button')
    // The navigate button should still work, but confirm/discard should be disabled
    const confirmBtn = screen.getByText('…').closest('button')!
    expect(confirmBtn).toBeDisabled()
  })
})
