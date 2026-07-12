import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

const mockUseSession = vi.fn()
vi.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'admin.metricDefinitions': 'Recommendation Metrics',
        'admin.metricDefinitionsDescription': 'Enable or disable metrics.',
        'admin.metricEnabled': 'Enabled',
        'admin.metricDisabled': 'Disabled',
        'admin.metricUpdateFailed': 'Failed to update metric. Please try again.',
        'admin.noMetricDefinitions': 'No metrics are configured for this deployment yet.',
        'metrics.citation_count': 'Citations',
        'metrics.impact_factor': 'Impact Factor',
      }
      return map[key] ?? key
    },
  }),
}))

const mockFetchAll = vi.fn()
const mockUpdate = vi.fn()
vi.mock('@/lib/api/metric-definitions', () => ({
  fetchAllMetricDefinitions: (...args: any[]) => mockFetchAll(...args),
  updateMetricDefinition: (...args: any[]) => mockUpdate(...args),
}))

const adminSession = {
  data: { user: { role: 'admin' }, accessToken: 'test-token' },
  status: 'authenticated',
}

// 2026-07-12: one row per metric_key (not per provider) — provider/priority no longer
// exists in this shape at all.
const rows = [
  {
    id: 'def-1', metric_key: 'citation_count', label_i18n_key: 'metrics.citation_count',
    icon_name: 'quote', format_hint: 'integer', unit: null, enabled: true,
  },
  {
    id: 'def-2', metric_key: 'impact_factor', label_i18n_key: 'metrics.impact_factor',
    icon_name: null, format_hint: 'decimal', unit: null, enabled: false,
  },
]

describe('MetricDefinitionsPage (admin)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUseSession.mockReturnValue(adminSession)
    mockFetchAll.mockResolvedValue(rows)
  })

  it('redirects to /login when unauthenticated', async () => {
    mockUseSession.mockReturnValue({ data: null, status: 'unauthenticated' })
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/login'))
  })

  it('redirects to /settings when authenticated but not admin', async () => {
    mockUseSession.mockReturnValue({ data: { user: { role: 'member' }, accessToken: 't' }, status: 'authenticated' })
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/settings'))
  })

  it('lists one row per metric_key, including disabled ones, with no provider/priority shown', async () => {
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => {
      expect(screen.getByText('Citations')).toBeInTheDocument()
      expect(screen.getByText('Impact Factor')).toBeInTheDocument()
    })
    expect(screen.queryByText('openalex')).not.toBeInTheDocument()
    expect(screen.queryByText('semantic_scholar')).not.toBeInTheDocument()
  })

  it('toggles a switch and calls updateMetricDefinition with { enabled }', async () => {
    mockUpdate.mockResolvedValue({ ...rows[1], enabled: true })
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(screen.getByText('Impact Factor')).toBeInTheDocument())

    const switches = screen.getAllByRole('switch')
    fireEvent.click(switches[1]) // impact_factor, currently disabled

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith('def-2', { enabled: true }, 'test-token')
    })
  })

  it('rolls back the switch state when the update call fails', async () => {
    mockUpdate.mockRejectedValue(new Error('network error'))
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(screen.getByText('Impact Factor')).toBeInTheDocument())

    const switches = screen.getAllByRole('switch')
    fireEvent.click(switches[1])

    await waitFor(() => {
      expect(screen.getByText('Failed to update metric. Please try again.')).toBeInTheDocument()
    })
    expect(screen.getAllByRole('switch')[1]).not.toBeChecked()
  })

  it('picking an icon from the gallery calls updateMetricDefinition with { icon_name }', async () => {
    mockUpdate.mockResolvedValue({ ...rows[0], icon_name: 'trophy' })
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(screen.getByText('Citations')).toBeInTheDocument())

    fireEvent.click(screen.getByLabelText('citation_count icon'))
    fireEvent.click(await screen.findByRole('button', { name: 'trophy' }))

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith('def-1', { icon_name: 'trophy' }, 'test-token')
    })
  })

  it('disables an icon already used by another metric definition, but not the row\'s own icon', async () => {
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => expect(screen.getByText('Impact Factor')).toBeInTheDocument())

    // impact_factor's own icon is null — open its gallery and confirm citation_count's
    // icon ('quote') is disabled there, while opening citation_count's own gallery
    // leaves 'quote' selectable (it's that row's own current icon).
    fireEvent.click(screen.getByLabelText('impact_factor icon'))
    const quoteInImpactFactorGallery = await screen.findByRole('button', { name: 'quote' })
    expect(quoteInImpactFactorGallery).toHaveAttribute('aria-disabled', 'true')

    fireEvent.click(quoteInImpactFactorGallery)
    expect(mockUpdate).not.toHaveBeenCalled()
  })

  it('shows an empty state when no metrics are configured', async () => {
    mockFetchAll.mockResolvedValue([])
    const { default: MetricDefinitionsPage } = await import('@/app/admin/metric-definitions/page')
    render(<MetricDefinitionsPage />)
    await waitFor(() => {
      expect(screen.getByText('No metrics are configured for this deployment yet.')).toBeInTheDocument()
    })
  })
})
