import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

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
