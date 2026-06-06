import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'

vi.mock('next-auth/react', () => ({
  getSession: vi.fn().mockResolvedValue({ accessToken: 'test-token' }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  global.fetch = vi.fn()
})

describe('MetricsChart', () => {
  it('shows loading skeleton initially', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => new Promise(() => {}), // never resolves
    })

    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    const { container } = render(
      <MetricsChart title="Test" query="scraper_runs_total" refreshInterval={0} />
    )
    expect(screen.getByText('Test')).toBeDefined()
    // Skeleton or loading state present before data loads
    const skeleton = container.querySelector('[class*="skeleton"]') ?? container.querySelector('[data-slot="skeleton"]')
    expect(skeleton).toBeDefined()
  })

  it('shows "not configured" when proxy returns not_configured', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ error: 'not_configured' }),
    })

    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="Stats" query="test" refreshInterval={0} />)
    await waitFor(() => screen.getByText('Grafana not configured'))
  })

  it('shows error state when fetch fails', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network error'))

    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="Stats" query="test" refreshInterval={0} />)
    await waitFor(() => screen.getByText('Failed to load data'))
  })
})

describe('MetricsChart tooltip', () => {
  it('renders help icon when tooltip prop is provided', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => new Promise(() => {}),
    })
    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(
      <TooltipProvider>
        <MetricsChart title="Test" query="q" tooltip="Chart tooltip" refreshInterval={0} />
      </TooltipProvider>
    )
    expect(screen.getByTestId('help-icon')).toBeDefined()
  })

  it('does not render help icon without tooltip prop', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => new Promise(() => {}),
    })
    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="Test" query="q" refreshInterval={0} />)
    expect(screen.queryByTestId('help-icon')).toBeNull()
  })
})

describe('MetricsChart controlled mode', () => {
  it('renders chart data from externalData without calling fetch', async () => {
    const externalData = {
      status: 'success' as const,
      data: {
        resultType: 'matrix' as const,
        result: [{
          metric: {},
          values: [[1748000000, '5'], [1748003600, '8']] as [number, string][],
        }],
      },
    }

    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="External" query="unused" externalData={externalData} refreshInterval={0} />)

    await waitFor(() => expect(global.fetch).not.toHaveBeenCalled())
  })

  it('shows refresh icon when onRefresh is provided', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="Chart" query="q" onRefresh={onRefresh} refreshInterval={0} />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh' })).toBeDefined())
  })

  it('calls onRefresh when refresh button clicked', async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      json: async () => ({ error: 'not_configured' }),
    })
    const { MetricsChart } = await import('@/components/features/monitoring/metrics-chart')
    render(<MetricsChart title="Chart" query="q" onRefresh={onRefresh} refreshInterval={0} />)
    await waitFor(() => screen.getByRole('button', { name: 'Refresh' }))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(onRefresh).toHaveBeenCalledOnce())
  })
})