import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    locale: 'en',
    t: (key: string) => {
      const map: Record<string, string> = {
        'tags.unsupervised': 'Unsupervised',
        'tags.semiSupervised': 'Semi-supervised',
        'tags.supervised': 'Supervised',
      }
      return map[key] ?? key
    },
  }),
}))

describe('TagModeSelector', () => {
  const defaultProps = {
    value: 'unsupervised' as const,
    onChange: vi.fn(),
  }

  it('renders all three mode buttons', async () => {
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector {...defaultProps} />)
    expect(screen.getByText('Unsupervised')).toBeInTheDocument()
    expect(screen.getByText('Semi-supervised')).toBeInTheDocument()
    expect(screen.getByText('Supervised')).toBeInTheDocument()
  })

  it('calls onChange when clicking a different mode', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector value="unsupervised" onChange={onChange} />)
    await user.click(screen.getByText('Semi-supervised'))
    expect(onChange).toHaveBeenCalledWith('semi_supervised')
  })

  it('disables buttons when disabled prop is true', async () => {
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector {...defaultProps} disabled />)
    const buttons = screen.getAllByRole('tab')
    buttons.forEach(btn => expect(btn).toBeDisabled())
  })

  // ── T044: Active/selected visual state ──────────────────────────────────────

  it('highlights the currently selected mode button', async () => {
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector value="semi_supervised" onChange={vi.fn()} />)
    const buttons = screen.getAllByRole('tab')
    // The semi-supervised button should have aria-selected or a distinct attribute
    const semiBtn = buttons.find(b => b.textContent?.includes('Semi-supervised'))
    expect(semiBtn).toBeTruthy()
    expect(semiBtn!.getAttribute('aria-selected')).toBe('true')
  })

  // ── T045: Mode selector persists change ──────────────────────────────────────

  it('triggers onChange callback that can be used to persist mode change', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector value="unsupervised" onChange={onChange} />)
    await user.click(screen.getByText('Supervised'))
    expect(onChange).toHaveBeenCalledWith('supervised')
  })

  // ── T068: Tag mode selector error handling ───────────────────────────────────

  it('calls onChange even when API might fail (component defers error handling to parent)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector value="unsupervised" onChange={onChange} />)
    await user.click(screen.getByText('Supervised'))
    // The component itself calls onChange; API error handling is the parent's responsibility
    expect(onChange).toHaveBeenCalledTimes(1)
  })
})
