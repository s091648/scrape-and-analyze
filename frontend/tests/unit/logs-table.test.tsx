import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
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

  it('does not misclassify a successful httpx request line as WARNING just because its URL embeds the word "warn"', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000',
            'HTTP Request: GET https://logs-prod.grafana.net/loki/api/v1/query_range?query=%7Bapp%3D%22scraper%22%7D+%7C+detected_level+%3D+%22warn%22 "HTTP/1.1 200 OK"',
          ]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('INFO')).toBeDefined()
      expect(screen.queryByText('WARNING')).toBeNull()
    })
  })

  it('classifies a failed httpx request line by its HTTP status code', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000',
            'HTTP Request: GET https://tempo-prod.grafana.net/tempo/api/search?q=unused "HTTP/1.1 400 Bad Request"',
          ]],
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

  it('does not call fetch with the placeholder query while externalData is null (pending)', async () => {
    // Regression test: a parent batch hook's initial "not loaded yet" state is
    // externalData={null} (not undefined) precisely so this component can tell
    // "controlled mode, still loading" apart from "no externalData prop at all,
    // please self-fetch" — self-fetching here would send the literal placeholder
    // query="unused" to Grafana and come back 400 Bad Request.
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Pending" query="unused" refreshInterval={0} externalData={null} />)
    await waitFor(() => expect(screen.getByText('Pending')).toBeDefined())
    expect(global.fetch).not.toHaveBeenCalled()
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

  it('renders entries from a successful self-fetch', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'success',
        data: {
          resultType: 'streams',
          result: [{
            stream: { env: 'production' },
            values: [['1700000000000000000', JSON.stringify({ level: 'info', event: 'self_fetched' })]],
          }],
        },
      }),
    })
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('self_fetched')).toBeDefined()
    })
  })

  it('shows error state when the self-fetch response is not a success status', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'error' }),
    })
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('admin.failedToLoadLogs')).toBeDefined()
    })
  })

  it('sets up a periodic refresh interval when refreshInterval is non-zero', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', data: { resultType: 'streams', result: [] } }),
    })
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')

    vi.useFakeTimers()
    try {
      let unmount: () => void
      await act(async () => {
        ;({ unmount } = render(<LogsTable title="Logs" query="{app='test'}" refreshInterval={30} />))
        await Promise.resolve()
      })
      expect(global.fetch).toHaveBeenCalledTimes(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000)
      })
      expect(global.fetch).toHaveBeenCalledTimes(2)

      unmount!()
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000)
      })
      expect(global.fetch).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('resolves an absolute (non "now-") time value as-is', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'success', data: { resultType: 'streams', result: [] } }),
    })
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable
        title="Logs"
        query="{app='test'}"
        from="1700000000000000000"
        to="1700000100000000000"
        refreshInterval={0}
      />
    )
    await waitFor(() => expect(screen.getByText('admin.noLogs')).toBeDefined())
    const calledUrl = String((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0])
    expect(calledUrl).toContain('1700000000000000000')
    expect(calledUrl).toContain('1700000100000000000')
  })
})

// ── Country / session_id columns + click-to-filter ──────────────────────────

describe('LogsTable country + session columns', () => {
  const requestRow = (extra: Record<string, unknown>) => ({
    status: 'success' as const,
    data: {
      resultType: 'streams' as const,
      result: [{
        stream: {},
        values: [[
          '1700000000000000000',
          JSON.stringify({ level: 'info', event: 'request', method: 'GET', path: '/articles', ...extra }),
        ]] as [string, string][],
      }],
    },
  })

  it('renders Country (resolved name) and Session (truncated) when showRequestColumns is set', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable title="Logs" query="" refreshInterval={0} showRequestColumns
        externalData={requestRow({ geo_country: 'TW', session_id: 'abcdef12-3456-7890-abcd-ef1234567890' })} />
    )
    await waitFor(() => {
      expect(screen.getByText('Taiwan')).toBeDefined()
      expect(screen.getByText('abcdef12…')).toBeDefined()
    })
  })

  it('does not render Country/Session columns without showRequestColumns', async () => {
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable title="Logs" query="" refreshInterval={0}
        externalData={requestRow({ geo_country: 'TW', session_id: 'abcdef12-3456' })} />
    )
    await waitFor(() => expect(screen.getByText('GET /articles')).toBeDefined())
    expect(screen.queryByText('Taiwan')).toBeNull()
  })

  it('clicking a country cell calls onLogFilterChange, and clicking the active one clears it', async () => {
    const onLogFilterChange = vi.fn()
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    const { rerender } = render(
      <LogsTable title="Logs" query="" refreshInterval={0} showRequestColumns
        externalData={requestRow({ geo_country: 'TW', session_id: 's1' })}
        onLogFilterChange={onLogFilterChange} />
    )
    await waitFor(() => expect(screen.getByText('Taiwan')).toBeDefined())

    fireEvent.click(screen.getByText('Taiwan'))
    expect(onLogFilterChange).toHaveBeenCalledWith({ type: 'country', value: 'TW' })

    rerender(
      <LogsTable title="Logs" query="" refreshInterval={0} showRequestColumns
        externalData={requestRow({ geo_country: 'TW', session_id: 's1' })}
        logFilter={{ type: 'country', value: 'TW' }}
        onLogFilterChange={onLogFilterChange} />
    )
    fireEvent.click(screen.getByText('Taiwan'))
    expect(onLogFilterChange).toHaveBeenLastCalledWith(null)
  })

  it('hides rows that do not match an active session logFilter', async () => {
    const external = {
      status: 'success' as const,
      data: {
        resultType: 'streams' as const,
        result: [{
          stream: {},
          values: [
            ['1700000002000000000', JSON.stringify({ level: 'info', event: 'keep_me', session_id: 'wanted' })],
            ['1700000001000000000', JSON.stringify({ level: 'info', event: 'drop_me', session_id: 'other' })],
          ] as [string, string][],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(
      <LogsTable title="Logs" query="" refreshInterval={0} showRequestColumns
        externalData={external} logFilter={{ type: 'session', value: 'wanted' }} />
    )
    await waitFor(() => {
      expect(screen.getByText('keep_me')).toBeDefined()
      expect(screen.queryByText('drop_me')).toBeNull()
    })
  })
})

// ── parseLevel edge cases ────────────────────────────────────────────────────

describe('LogsTable parseLevel edge cases', () => {
  it('recognizes an explicit "INFO:" prefix', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{ stream: {}, values: [['1700000000000000000', 'INFO: server started']] }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => expect(screen.getByText('INFO')).toBeDefined())
  })

  it('falls back to info for an unstructured line with no level signal at all', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{ stream: {}, values: [['1700000000000000000', 'just a plain unstructured line']] }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => expect(screen.getByText('INFO')).toBeDefined())
  })
})

// ── parseMessage "request" event formatting ──────────────────────────────────

describe('LogsTable parseMessage request formatting', () => {
  it('formats a "request" event as "METHOD path → status (duration)"', async () => {
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [[
            '1700000000000000000',
            JSON.stringify({ level: 'info', event: 'request', method: 'GET', path: '/api/articles', status_code: 200, duration_ms: 42 }),
          ]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('GET /api/articles → 200 (42ms)')).toBeDefined()
    })
  })
})

// ── Trace navigation from a log row ──────────────────────────────────────────

describe('LogsTable trace navigation', () => {
  function mockFetchRouter(handlers: { logs?: unknown; trace?: unknown | (() => Promise<unknown>) }) {
    global.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/grafana/traces/')) {
        if (typeof handlers.trace === 'function') return (handlers.trace as () => Promise<unknown>)()
        if (handlers.trace instanceof Error) throw handlers.trace
        return { ok: true, json: async () => handlers.trace }
      }
      return { ok: true, json: async () => handlers.logs ?? { streams: [] } }
    }) as unknown as typeof fetch
  }

  it('opens the ArticleWorkflowDialog when the trace contains an article.pipeline span', async () => {
    mockFetchRouter({
      trace: {
        batches: [{
          resource: { attributes: [] },
          scopeSpans: [{
            spans: [
              {
                traceId: 't1', spanId: 'aaaa1111', parentSpanId: '', name: 'article.pipeline',
                startTimeUnixNano: '1', endTimeUnixNano: '2', attributes: [],
              },
              {
                traceId: 't1', spanId: 'bbbb2222', parentSpanId: 'aaaa1111', name: 'article.processed.handle',
                startTimeUnixNano: '1', endTimeUnixNano: '2', attributes: [],
              },
            ],
          }],
        }],
      },
    })
    // span_id points at the stage span, not the pipeline itself — exercises
    // findPipelineForSpan()'s walk-up-the-parent-chain loop. IDs are kept
    // hex-only (0-9a-f) so otlpIdToHex() takes its "already hex" branch
    // deterministically, rather than its base64-decode fallback.
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', JSON.stringify({
            level: 'info', event: 'article_analyzed', trace_id: 't1', span_id: 'bbbb2222',
          })]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('article_analyzed')).toBeDefined())
    fireEvent.click(screen.getAllByText('article_analyzed')[0].closest('tr')!)

    const traceLink = await screen.findByRole('button', { name: /admin\.viewInTrace/ })
    fireEvent.click(traceLink)

    await waitFor(() => {
      expect(screen.getByTestId('article-workflow-dialog')).toBeDefined()
    })

    fireEvent.click(screen.getByText('close'))
    await waitFor(() => {
      expect(screen.queryByTestId('article-workflow-dialog')).toBeNull()
    })
  })

  it('falls back to the first pipeline span when span_id has no pipeline ancestor of its own', async () => {
    mockFetchRouter({
      trace: {
        batches: [{
          resource: { attributes: [] },
          scopeSpans: [{
            spans: [
              {
                traceId: 't4', spanId: 'aaaa4444', parentSpanId: '', name: 'article.pipeline',
                startTimeUnixNano: '1', endTimeUnixNano: '2', attributes: [],
              },
              // Unrelated root-level span with no parent and no pipeline ancestor —
              // findPipelineForSpan() must walk to the end of its own chain and give up.
              {
                traceId: 't4', spanId: 'dddd4444', parentSpanId: '', name: 'pipeline.discover',
                startTimeUnixNano: '1', endTimeUnixNano: '2', attributes: [],
              },
            ],
          }],
        }],
      },
    })
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', JSON.stringify({
            level: 'info', event: 'discover_done', trace_id: 't4', span_id: 'dddd4444',
          })]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('discover_done')).toBeDefined())
    fireEvent.click(screen.getAllByText('discover_done')[0].closest('tr')!)

    const traceLink = await screen.findByRole('button', { name: /admin\.viewInTrace/ })
    fireEvent.click(traceLink)

    await waitFor(() => {
      expect(screen.getByTestId('article-workflow-dialog')).toBeDefined()
    })
  })

  it('falls back to the generic waterfall dialog when the trace has no article.pipeline span', async () => {
    mockFetchRouter({
      trace: {
        batches: [{
          resource: { attributes: [] },
          scopeSpans: [{
            spans: [{
              traceId: 't2', spanId: 'cccc3333', parentSpanId: '', name: 'scraper.run',
              startTimeUnixNano: '1', endTimeUnixNano: '2', attributes: [],
            }],
          }],
        }],
      },
    })
    // span_id set to the (non-pipeline) root span with no parent — exercises
    // findPipelineForSpan()'s "chain exhausted, no pipeline ancestor found" path.
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', JSON.stringify({
            level: 'info', event: 'run_completed', trace_id: 't2', span_id: 'cccc3333',
          })]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('run_completed')).toBeDefined())
    fireEvent.click(screen.getAllByText('run_completed')[0].closest('tr')!)

    const traceLink = await screen.findByRole('button', { name: /admin\.viewInTrace/ })
    fireEvent.click(traceLink)

    await waitFor(() => {
      expect(screen.getByText('admin.waterfallDialogTitle')).toBeDefined()
    })

    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByText('admin.waterfallDialogTitle')).toBeNull()
    })
  })

  it('shows a failure dialog when loading the trace throws', async () => {
    mockFetchRouter({ trace: new Error('trace fetch failed') })
    const external: LokiResponse = {
      status: 'success',
      data: {
        resultType: 'streams',
        result: [{
          stream: {},
          values: [['1700000000000000000', JSON.stringify({
            level: 'info', event: 'run_failed', trace_id: 't3',
          })]],
        }],
      },
    }
    const { LogsTable } = await import('@/components/features/monitoring/logs-table')
    render(<LogsTable title="Logs" query="" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('run_failed')).toBeDefined())
    fireEvent.click(screen.getAllByText('run_failed')[0].closest('tr')!)

    const traceLink = await screen.findByRole('button', { name: /admin\.viewInTrace/ })
    fireEvent.click(traceLink)

    await waitFor(() => {
      expect(screen.getByText('admin.traceLoadFailedTitle')).toBeDefined()
    })

    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByText('admin.traceLoadFailedTitle')).toBeNull()
    })
  })
})
