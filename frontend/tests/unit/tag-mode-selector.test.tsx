import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

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
    const onChange = vi.fn()
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector value="unsupervised" onChange={onChange} />)
    fireEvent.click(screen.getByText('Semi-supervised'))
    expect(onChange).toHaveBeenCalledWith('semi_supervised')
  })

  it('disables buttons when disabled prop is true', async () => {
    const { TagModeSelector } = await import('@/components/features/tags/tag-mode-selector')
    render(<TagModeSelector {...defaultProps} disabled />)
    const buttons = screen.getAllByRole('tab')
    buttons.forEach(btn => expect(btn).toBeDisabled())
  })
})
