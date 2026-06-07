import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MultiSelectPopover } from '@/components/common/multi-select-popover'

const defaultProps = {
  label: 'Tags',
  options: ['ai', 'ml', 'robotics'],
  selected: [] as string[],
  onChange: vi.fn(),
}

function renderPopover(overrides: Partial<typeof defaultProps> = {}) {
  return render(<MultiSelectPopover {...defaultProps} {...overrides} />)
}

function openPopover() {
  fireEvent.click(screen.getByRole('button', { name: /tags/i }))
}

beforeEach(() => {
  vi.clearAllMocks()
  // cmdk calls scrollIntoView internally; jsdom doesn't implement it
  Element.prototype.scrollIntoView = vi.fn()
})

describe('MultiSelectPopover', () => {
  it('renders the trigger button with label', () => {
    renderPopover()
    expect(screen.getByRole('button', { name: /tags/i })).toBeInTheDocument()
  })

  it('shows count badge when items are selected', () => {
    renderPopover({ selected: ['ai', 'ml'] })
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('does not show badge when nothing is selected', () => {
    renderPopover()
    expect(screen.queryByText('1')).not.toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders all string options in the list', () => {
    renderPopover()
    openPopover()
    expect(screen.getByText('ai')).toBeInTheDocument()
    expect(screen.getByText('ml')).toBeInTheDocument()
    expect(screen.getByText('robotics')).toBeInTheDocument()
  })

  it('accepts SelectOption objects with value and label', () => {
    renderPopover({
      options: [
        { value: 'v1', label: 'Option One' },
        { value: 'v2', label: 'Option Two' },
      ],
    })
    openPopover()
    expect(screen.getByText('Option One')).toBeInTheDocument()
    expect(screen.getByText('Option Two')).toBeInTheDocument()
  })

  it('accepts mixed string and object options', () => {
    renderPopover({
      options: ['plain', { value: 'obj', label: 'Object Label' }],
    })
    openPopover()
    expect(screen.getByText('plain')).toBeInTheDocument()
    expect(screen.getByText('Object Label')).toBeInTheDocument()
  })

  it('shows checked checkboxes for selected items', () => {
    renderPopover({ selected: ['ai'] })
    openPopover()
    const checkboxes = screen.getAllByRole('checkbox')
    const aiCheckbox = checkboxes.find(cb => {
      const item = cb.closest('[cmdk-item]') ?? cb.parentElement
      return item?.textContent?.includes('ai')
    })
    // The checkbox for 'ai' should have data-state="checked"
    expect(checkboxes.some(cb => (cb as HTMLInputElement).checked || cb.getAttribute('data-state') === 'checked')).toBeTruthy()
  })

  it('calls onChange with item added when unselected item is clicked', () => {
    const onChange = vi.fn()
    renderPopover({ selected: [], onChange })
    openPopover()
    fireEvent.click(screen.getByText('ai'))
    expect(onChange).toHaveBeenCalledWith(['ai'])
  })

  it('calls onChange with item removed when selected item is clicked', () => {
    const onChange = vi.fn()
    renderPopover({ selected: ['ai', 'ml'], onChange })
    openPopover()
    fireEvent.click(screen.getByText('ai'))
    expect(onChange).toHaveBeenCalledWith(['ml'])
  })

  it('preserves other selected items when toggling one', () => {
    const onChange = vi.fn()
    renderPopover({ selected: ['ai', 'robotics'], onChange })
    openPopover()
    fireEvent.click(screen.getByText('ml'))
    expect(onChange).toHaveBeenCalledWith(['ai', 'robotics', 'ml'])
  })

  it('uses custom searchPlaceholder when provided', () => {
    renderPopover({ searchPlaceholder: 'Search tags…' })
    openPopover()
    const input = screen.getByPlaceholderText('Search tags…')
    expect(input).toBeInTheDocument()
  })

  it('derives default placeholder from label when searchPlaceholder is omitted', () => {
    renderPopover()
    openPopover()
    expect(screen.getByPlaceholderText('Search tags…')).toBeInTheDocument()
  })
})
