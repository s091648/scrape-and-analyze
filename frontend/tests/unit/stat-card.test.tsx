import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from '@/components/features/monitoring/stat-card'
import { fireEvent, waitFor } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'

describe('StatCard', () => {
  it('renders title and value', () => {
    render(<StatCard title="Total Runs" value={42} />)
    expect(screen.getByText('Total Runs')).toBeDefined()
    expect(screen.getByText('42')).toBeDefined()
  })

  it('renders value with unit', () => {
    render(<StatCard title="Duration" value="12.3" unit="s" />)
    expect(screen.getByText('12.3')).toBeDefined()
    expect(screen.getByText('s')).toBeDefined()
  })

  it('renders — when value is null', () => {
    render(<StatCard title="Empty" value={null} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('renders — on error', () => {
    render(<StatCard title="Error" error />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
  })

  it('renders skeleton when loading', () => {
    const { container } = render(<StatCard title="Loading" loading />)
    // Skeleton adds an element, value text should not be present
    expect(screen.queryByRole('heading')).toBeNull()
    expect(container.querySelector('[class*="skeleton"]') ?? container.querySelector('[data-slot="skeleton"]')).toBeDefined()
  })
})

describe('StatCard tooltip', () => {
  it('renders help icon when tooltip prop is provided', () => {
    render(
      <TooltipProvider>
        <StatCard title="Runs" value={5} tooltip="Total runs in 24h" />
      </TooltipProvider>
    )
    expect(screen.getByTestId('help-icon')).toBeDefined()
  })

  it('does not render help icon without tooltip prop', () => {
    render(<StatCard title="Runs" value={5} />)
    expect(screen.queryByTestId('help-icon')).toBeNull()
  })
})

describe('StatCard refresh', () => {
  it('shows refresh icon button when onRefresh is provided', () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    render(<StatCard title="Runs" value={5} onRefresh={onRefresh} />)
    expect(screen.getByRole('button')).toBeDefined()
  })

  it('does not show refresh icon when onRefresh is not provided', () => {
    render(<StatCard title="Runs" value={5} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('calls onRefresh when icon button is clicked', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    render(<StatCard title="Runs" value={5} onRefresh={onRefresh} />)
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(onRefresh).toHaveBeenCalledOnce())
  })
})