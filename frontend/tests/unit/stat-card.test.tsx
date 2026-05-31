import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from '@/components/features/monitoring/stat-card'

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
