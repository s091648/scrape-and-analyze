import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { LokiResponse } from '@/lib/api/grafana'

vi.mock('next-auth/react', () => ({
  getSession: vi.fn().mockResolvedValue({ accessToken: 'test-token' }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))

vi.mock('@/components/features/monitoring/article-workflow-dialog', () => ({
  ArticleWorkflowDialog: ({ open, onClose }: any) =>
    open ? <div data-testid="article-workflow-dialog"><button onClick={onClose}>close</button></div> : null,
}))

// NOTE: @/lib/api/grafana is intentionally NOT mocked here;
// the real queryLogs / queryTraceById call global.fetch which is mocked in beforeEach.
// Tests that need queryTraceById to return specific data must configure global.fetch accordingly.

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => ({ streams: [] }),
  })
})

// ── Tooltip tests (existing) ──────────────────────────────────────────────────

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

// ── externalData rendering ────────────────────────────────────────────────────

describe('LogsTable with externalData', () => {
  it('shows not-configured message for error externalData', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable
        title="Logs"
        query=""
        refreshInterval={0}
        externalData={{ error: 'not_configured' } as any}
      />
    )
    await waitFor(() => {
      expect(screen.getByText('admin.grafanaNotConfigured')).toBeDefined()
    })
  })

  it('shows error state for non-success externalData', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable
        title="Logs"
        query=""
        refreshInterval={0}
        externalData={{ status: 'error' } as any}
      />
    )
    await waitFor(() => {
      expect(screen.getByText('admin.failedToLoadLogs')).toBeDefined()
    })
  })

  it('shows "no logs" when externalData has empty streams', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: { resultType: 'streams', result: [] },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('admin.noLogs')).toBeDefined()
    })
  })

  it('renders log entries from externalData streams', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { env: 'production' },
          values: [
            ['1700000000000000000', JSON.stringify({ level: 'info', event: 'article_analyzed' })],
          ],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('article_analyzed')).toBeDefined()
      expect(screen.getByText('INFO')).toBeDefined()
      expect(screen.getByText('production')).toBeDefined()
    })
  })

  it('renders log details from JSON with priority fields', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: { env: 'local' },
          values: [
            [
              '1700000001000000000',
              JSON.stringify({
                level: 'info',
                event: 'fetch_complete',
                url: 'https://example.com/very/long/article/url/that/should/be/truncated',
              }),
            ],
          ],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('fetch_complete')).toBeDefined()
    })
    // Details row should show url: ... (truncated)
    const details = screen.getByText(/url:/)
    expect(details).toBeDefined()
  })

  it('renders log level for non-JSON error line', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', 'ERROR: something went wrong']],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('ERROR')).toBeDefined()
    })
  })

  it('renders log level for non-JSON warning line', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', 'WARN: disk usage high']],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('WARNING')).toBeDefined()
    })
  })

  it('renders multiple entries sorted by timestamp descending', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [
            ['1700000001000000000', JSON.stringify({ level: 'info', event: 'second' })],
            ['1700000000000000000', JSON.stringify({ level: 'info', event: 'first' })],
          ],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      const rows = screen.getAllByRole('row')
      // Header row + 2 data rows; "second" should appear before "first"
      const secondIdx = rows.findIndex(r => r.textContent?.includes('second'))
      const firstIdx  = rows.findIndex(r => r.textContent?.includes('first'))
      expect(secondIdx).toBeLessThan(firstIdx)
    })
  })

  it('filters entries by forcedLevel', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [
            ['1700000001000000000', JSON.stringify({ level: 'error', event: 'err_event' })],
            ['1700000000000000000', JSON.stringify({ level: 'info',  event: 'ok_event' })],
          ],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable
        title="Logs"
        query=""
        refreshInterval={0}
        externalData={external}
        forcedLevel="error"
      />
    )
    await waitFor(() => {
      expect(screen.getByText('err_event')).toBeDefined()
      expect(screen.queryByText('ok_event')).toBeNull()
    })
  })

  it('opens LogDetailDialog when a log row is clicked', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', JSON.stringify({ level: 'info', event: 'click_me' })]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getAllByText('click_me').length).toBeGreaterThan(0))
    const rows = screen.getAllByText('click_me')
    fireEvent.click(rows[0].closest('tr')!)

    // After click, the real LogDetailDialog opens — 'click_me' appears in multiple places
    await waitFor(() => {
      expect(screen.getAllByText('click_me').length).toBeGreaterThan(1)
    })
  })
})

// ── Self-fetch mode ───────────────────────────────────────────────────────────

describe('LogsTable self-fetch mode', () => {
  it('shows not-configured when fetch returns not_configured', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ error: 'not_configured' }),
    })
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('admin.grafanaNotConfigured')).toBeDefined()
    })
  })

  it('shows error state when fetch throws', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network'))
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('admin.failedToLoadLogs')).toBeDefined()
    })
  })
})
