import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('next-auth/react', () => ({
  getSession: vi.fn().mockResolvedValue({ accessToken: 'test-token' }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => ({ traces: [] }),
  })
})

describe('TracesTable tooltip', () => {
  it('renders help icon when tooltip prop is provided', async () => {
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(
      <TooltipProvider>
        <TracesTable title="Traces" tooltip="Traces tooltip" refreshInterval={0} />
      </TooltipProvider>
    )
    expect(screen.getByTestId('help-icon')).toBeDefined()
  })

  it('does not render help icon without tooltip prop', async () => {
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} />)
    expect(screen.queryByTestId('help-icon')).toBeNull()
  })
})
