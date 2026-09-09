import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LogFilterChip } from '@/components/features/monitoring/log-filter-chip'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: 'en' }),
}))

describe('LogFilterChip', () => {
  it('renders nothing when there is no active filter', () => {
    const { container } = render(<LogFilterChip filter={null} onClear={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('resolves an ISO country code to its display name for a country filter', () => {
    render(<LogFilterChip filter={{ type: 'country', value: 'US' }} onClear={() => {}} />)
    expect(screen.getByText('admin.logColumnCountry:')).toBeDefined()
    expect(screen.getByText('United States of America')).toBeDefined()
  })

  it('falls back to the raw code when the country is unknown', () => {
    render(<LogFilterChip filter={{ type: 'country', value: 'ZZ' }} onClear={() => {}} />)
    expect(screen.getByText('ZZ')).toBeDefined()
  })

  it('shows the raw value verbatim for a session filter', () => {
    render(<LogFilterChip filter={{ type: 'session', value: 'abc12345-de' }} onClear={() => {}} />)
    expect(screen.getByText('admin.logColumnSession:')).toBeDefined()
    expect(screen.getByText('abc12345-de')).toBeDefined()
  })

  it('calls onClear when the clear button is clicked', () => {
    const onClear = vi.fn()
    render(<LogFilterChip filter={{ type: 'session', value: 's-1' }} onClear={onClear} />)
    fireEvent.click(screen.getByRole('button', { name: 'admin.logFilterClear' }))
    expect(onClear).toHaveBeenCalledOnce()
  })
})
