import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DateFilter } from '@/components/common/date-filter'

const labels = {
  any: 'Any',
  after: 'After',
  before: 'Before',
  range: 'Range',
  recent: 'Recent',
  from: 'From',
  to: 'To',
  days: 'days',
}

const defaultProps = {
  label: 'Date',
  after: '',
  before: '',
  onAfterChange: vi.fn(),
  onBeforeChange: vi.fn(),
  labels,
}

function renderFilter(overrides: Partial<typeof defaultProps> = {}) {
  return render(<DateFilter {...defaultProps} {...overrides} />)
}

function openPopover() {
  fireEvent.click(screen.getByRole('button', { name: /date/i }))
}

beforeEach(() => vi.clearAllMocks())

describe('DateFilter', () => {
  it('renders the trigger button with label', () => {
    renderFilter()
    expect(screen.getByRole('button', { name: /date/i })).toBeInTheDocument()
  })

  it('shows badge when after date is set', () => {
    renderFilter({ after: '2024-01-01' })
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('shows badge when before date is set', () => {
    renderFilter({ before: '2024-12-31' })
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('does not show badge when no date is set', () => {
    renderFilter()
    expect(screen.queryByText('1')).not.toBeInTheDocument()
  })

  it('initialises to "after" mode when only after is set', () => {
    renderFilter({ after: '2024-01-01', before: '' })
    openPopover()
    // After button should be active — it has bg-primary class
    const afterBtn = screen.getByRole('button', { name: 'After' })
    expect(afterBtn.className).toContain('bg-primary')
  })

  it('initialises to "before" mode when only before is set', () => {
    renderFilter({ after: '', before: '2024-12-31' })
    openPopover()
    const beforeBtn = screen.getByRole('button', { name: 'Before' })
    expect(beforeBtn.className).toContain('bg-primary')
  })

  it('initialises to "range" mode when both dates are set', () => {
    renderFilter({ after: '2024-01-01', before: '2024-12-31' })
    openPopover()
    const rangeBtn = screen.getByRole('button', { name: 'Range' })
    expect(rangeBtn.className).toContain('bg-primary')
  })

  it('initialises to "any" mode when no dates are set', () => {
    renderFilter()
    openPopover()
    const anyBtn = screen.getByRole('button', { name: 'Any' })
    expect(anyBtn.className).toContain('bg-primary')
  })

  it('clicking "any" mode calls both change handlers with empty string', () => {
    const onAfterChange = vi.fn()
    const onBeforeChange = vi.fn()
    renderFilter({ after: '2024-01-01', onAfterChange, onBeforeChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Any' }))
    expect(onAfterChange).toHaveBeenCalledWith('')
    expect(onBeforeChange).toHaveBeenCalledWith('')
  })

  it('clicking "before" mode clears after via onAfterChange', () => {
    const onAfterChange = vi.fn()
    const onBeforeChange = vi.fn()
    renderFilter({ after: '2024-01-01', onAfterChange, onBeforeChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Before' }))
    expect(onAfterChange).toHaveBeenCalledWith('')
  })

  it('clicking "after" mode clears before via onBeforeChange', () => {
    const onAfterChange = vi.fn()
    const onBeforeChange = vi.fn()
    renderFilter({ before: '2024-12-31', onAfterChange, onBeforeChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'After' }))
    expect(onBeforeChange).toHaveBeenCalledWith('')
  })

  it('switching to "recent" mode calls onAfterChange with a date string', () => {
    const onAfterChange = vi.fn()
    const onBeforeChange = vi.fn()
    renderFilter({ onAfterChange, onBeforeChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Recent' }))
    expect(onAfterChange).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/))
    expect(onBeforeChange).toHaveBeenCalledWith('')
  })

  it('shows days number input when mode is "recent"', () => {
    renderFilter()
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Recent' }))
    expect(screen.getByRole('spinbutton')).toBeInTheDocument()
    expect(screen.getByText('days')).toBeInTheDocument()
  })

  it('changing days input calls onAfterChange with updated date', () => {
    const onAfterChange = vi.fn()
    renderFilter({ onAfterChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Recent' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '7' } })
    expect(onAfterChange).toHaveBeenCalled()
    // Should receive a date string
    const lastCall = onAfterChange.mock.calls.at(-1)![0]
    expect(lastCall).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('clamps days to minimum of 1', () => {
    const onAfterChange = vi.fn()
    renderFilter({ onAfterChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Recent' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '0' } })
    expect(onAfterChange).toHaveBeenCalled()
  })

  it('clamps days to maximum of 180', () => {
    const onAfterChange = vi.fn()
    renderFilter({ onAfterChange })
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Recent' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '999' } })
    expect(onAfterChange).toHaveBeenCalled()
  })

  it('shows "From" date input when mode is "after"', () => {
    renderFilter()
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'After' }))
    expect(screen.getByText('From')).toBeInTheDocument()
    expect(screen.getByDisplayValue('')).toBeInTheDocument()
  })

  it('shows "To" date input when mode is "before"', () => {
    renderFilter()
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Before' }))
    expect(screen.getByText('To')).toBeInTheDocument()
  })

  it('shows both "From" and "To" date inputs when mode is "range"', () => {
    renderFilter()
    openPopover()
    fireEvent.click(screen.getByRole('button', { name: 'Range' }))
    expect(screen.getByText('From')).toBeInTheDocument()
    expect(screen.getByText('To')).toBeInTheDocument()
  })

  it('calls onAfterChange when "From" date input changes', () => {
    const onAfterChange = vi.fn()
    renderFilter({ after: '2024-01-01', onAfterChange })
    openPopover()
    const dateInput = screen.getAllByDisplayValue('2024-01-01')[0]
    fireEvent.change(dateInput, { target: { value: '2024-03-15' } })
    expect(onAfterChange).toHaveBeenCalledWith('2024-03-15')
  })

  it('calls onBeforeChange when "To" date input changes', () => {
    const onBeforeChange = vi.fn()
    renderFilter({ before: '2024-12-31', onBeforeChange })
    openPopover()
    const dateInput = screen.getAllByDisplayValue('2024-12-31')[0]
    fireEvent.change(dateInput, { target: { value: '2024-06-30' } })
    expect(onBeforeChange).toHaveBeenCalledWith('2024-06-30')
  })
})
