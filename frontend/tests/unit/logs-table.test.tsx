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
    json: async () => ({ streams: [] }),
  })
})

describe('LogsTable tooltip', () => {
  it('renders help icon when tooltip prop is provided', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <TooltipProvider>
        <LogsTable title="Logs" query="{app='test'}" tooltip="Log table tooltip" refreshInterval={0} />
      </TooltipProvider>
    )
    expect(screen.getByTestId('help-icon')).toBeDefined()
  })

  it('does not render help icon without tooltip prop', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={0} />)
    expect(screen.queryByTestId('help-icon')).toBeNull()
  })
})
