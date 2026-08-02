import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { TempoResponse } from '@/lib/api/grafana'

vi.mock('next-auth/react', () => ({
  getSession: vi.fn().mockResolvedValue({ accessToken: 'test-token' }),
}))

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: 'en' }),
}))

vi.mock('@/components/features/monitoring/run-waterfall-dialog', () => ({
  RunWaterfallDialog: ({ open, onClose, onSelectArticle, onSelectTopic }: any) =>
    open ? (
      <div data-testid="waterfall-dialog">
        <button onClick={onClose}>close waterfall</button>
        {onSelectArticle && (
          <button onClick={() => onSelectArticle({}, [])}>select article</button>
        )}
        {onSelectTopic && (
          <button onClick={() => onSelectTopic({}, [])}>select topic</button>
        )}
      </div>
    ) : null,
}))

vi.mock('@/components/features/monitoring/article-workflow-dialog', () => ({
  ArticleWorkflowDialog: ({ open, onClose }: any) =>
    open ? (
      <div data-testid="workflow-dialog">
        <button onClick={onClose}>close workflow</button>
      </div>
    ) : null,
}))

vi.mock('@/components/features/monitoring/weekly-report-topic-dialog', () => ({
  WeeklyReportTopicDialog: ({ open, onClose }: any) =>
    open ? (
      <div data-testid="topic-workflow-dialog">
        <button onClick={onClose}>close topic workflow</button>
      </div>
    ) : null,
}))

vi.mock('@/components/features/articles/article-detail-dialog', () => ({
  ArticleDetailDialog: ({ open, onOpenChange }: any) =>
    open ? (
      <div data-testid="article-detail-dialog">
        <button onClick={() => onOpenChange(false)}>close article</button>
      </div>
    ) : null,
}))

vi.mock('@/lib/api/articles', () => ({
  fetchArticleById: vi.fn().mockResolvedValue(null),
}))

vi.mock('@/lib/api/grafana', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/grafana')>()
  return {
    ...actual,
    queryTraces: vi.fn(),
    queryTraceById: vi.fn(),
  }
})

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => ({ traces: [] }),
  })
})

// ── Tooltip tests (existing) ──────────────────────────────────────────────────

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

// ── externalData rendering ────────────────────────────────────────────────────

describe('TracesTable with externalData', () => {
  it('shows not-configured for error externalData', async () => {
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(
      <TracesTable
        title="Traces"
        refreshInterval={0}
        externalData={{ error: 'not_configured' } as any}
      />
    )
    await waitFor(() => {
      expect(screen.getByText('admin.grafanaNotConfigured')).toBeDefined()
    })
  })

  it('shows "no traces" when externalData has empty traces', async () => {
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(
      <TracesTable
        title="Traces"
        refreshInterval={0}
        externalData={{ traces: [] }}
      />
    )
    await waitFor(() => {
      expect(screen.getByText('admin.noTraces')).toBeDefined()
    })
  })

  it('renders trace rows from externalData', async () => {
    const external: TempoResponse = {
      traces: [{
        traceID: 'abc123def456789012',
        rootServiceName: 'backend',
        rootTraceName: 'scraper.run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 5432,
      }],
    }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      // Shows first 8 chars of traceID
      expect(screen.getByText('abc123de…')).toBeDefined()
      expect(screen.getByText('backend')).toBeDefined()
      expect(screen.getByText('scraper.run')).toBeDefined()
    })
  })

  it('shows environment from spanSet attributes', async () => {
    const external: TempoResponse = {
      traces: [{
        traceID: 'trace001',
        rootServiceName: 'backend',
        rootTraceName: 'scraper.run',
        startTimeUnixNano: '1700000000000000000',
        spanSet: {
          spans: [{
            spanID: 's1',
            startTimeUnixNano: '1700000000000000000',
            durationNanos: '1000000000',
            attributes: [
              { key: 'deployment.environment', value: { stringValue: 'production' } },
            ],
          }],
          matched: 1,
        },
      }],
    }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('production')).toBeDefined()
    })
  })

  it('resolves duration from durationNanos fallback when durationMs is absent', async () => {
    const external: TempoResponse = {
      traces: [{
        traceID: 'trace002',
        rootServiceName: 'svc',
        rootTraceName: 'scraper.run',
        startTimeUnixNano: '1700000000000000000',
        spanSet: {
          spans: [{
            spanID: 's1',
            startTimeUnixNano: '1700000000000000000',
            durationNanos: '2500000000', // 2500 ms = 2.5 s
          }],
          matched: 1,
        },
      }],
    }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)
    await waitFor(() => {
      expect(screen.getByText('2.5 s')).toBeDefined()
    })
  })
})

// ── Expand/collapse ───────────────────────────────────────────────────────────

describe('TracesTable expand/collapse', () => {
  it('expands trace row to show article sub-rows', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce({
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{
          spans: [
            {
              traceId: 'trace001',
              spanId: 'root001',
              parentSpanId: '',
              name: 'scraper.run',
              startTimeUnixNano: '1700000000000000000',
              endTimeUnixNano: '1700000010000000000',
              attributes: [],
              status: { code: 0 },
            },
            {
              traceId: 'trace001',
              spanId: 'art001',
              parentSpanId: 'root001',
              name: 'article.pipeline',
              startTimeUnixNano: '1700000001000000000',
              endTimeUnixNano: '1700000002000000000',
              attributes: [
                { key: 'article.url', value: { stringValue: 'https://ex.com/a' } },
              ],
              status: { code: 0 },
            },
          ],
        }],
      }],
    })

    const external: TempoResponse = {
      traces: [{
        traceID: 'trace001',
        rootServiceName: 'backend',
        rootTraceName: 'scraper.run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 10000,
      }],
    }

    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('trace001…')).toBeDefined())

    // Click expand button
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => {
      expect(screen.getByText('view →')).toBeDefined()
    })
  })

  it('collapses an expanded trace row', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValue({
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{ spans: [] }],
      }],
    })

    const external: TempoResponse = {
      traces: [{
        traceID: 'trace001',
        rootServiceName: 'svc',
        rootTraceName: 'run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 1000,
      }],
    }

    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByLabelText('Expand')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(screen.getByLabelText('Collapse')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Collapse'))
    await waitFor(() => expect(screen.getByLabelText('Expand')).toBeDefined())
  })
})

// ── Waterfall dialog ──────────────────────────────────────────────────────────

describe('TracesTable waterfall dialog', () => {
  it('opens waterfall dialog when traceId link is clicked (detail already loaded)', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    const traceData = {
      batches: [{ resource: { attributes: [] }, scopeSpans: [{ spans: [] }] }],
    }
    queryTraceById.mockResolvedValue(traceData)

    const external: TempoResponse = {
      traces: [{
        traceID: 'trace999',
        rootServiceName: 'backend',
        rootTraceName: 'run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 500,
      }],
    }

    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('trace999…')).toBeDefined())

    // First expand to load detail
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(queryTraceById).toHaveBeenCalled())

    // Then click the trace ID link to open waterfall
    fireEvent.click(screen.getByText('trace999…'))
    await waitFor(() => {
      expect(screen.getByTestId('waterfall-dialog')).toBeDefined()
    })
  })

  it('closes waterfall dialog', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValue({
      batches: [{ resource: { attributes: [] }, scopeSpans: [{ spans: [] }] }],
    })

    const external: TempoResponse = {
      traces: [{
        traceID: 'trace888',
        rootServiceName: 'svc',
        rootTraceName: 'run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 100,
      }],
    }

    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('trace888…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(queryTraceById).toHaveBeenCalled())

    fireEvent.click(screen.getByText('trace888…'))
    await waitFor(() => expect(screen.getByTestId('waterfall-dialog')).toBeDefined())

    fireEvent.click(screen.getByText('close waterfall'))
    await waitFor(() => expect(screen.queryByTestId('waterfall-dialog')).toBeNull())
  })
})

// ── Weekly report run branch ──────────────────────────────────────────────────

describe('TracesTable weekly report run', () => {
  function weeklyReportTrace(traceID: string) {
    return {
      traceID,
      rootServiceName: 'backend',
      rootTraceName: 'weekly_report.run',
      startTimeUnixNano: '1700000000000000000',
      durationMs: 8000,
    }
  }

  function mockWeeklyReportDetail(overrides?: { topicAttrs?: any[] }) {
    return {
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{
          spans: [
            {
              traceId: 'wtrace01',
              spanId: 'root001',
              parentSpanId: '',
              name: 'weekly_report.run',
              startTimeUnixNano: '1700000000000000000',
              endTimeUnixNano: '1700000008000000000',
              attributes: [],
              status: { code: 0 },
            },
            {
              traceId: 'wtrace01',
              spanId: 'topic001',
              parentSpanId: 'root001',
              name: 'weekly_report.topic',
              startTimeUnixNano: '1700000001000000000',
              endTimeUnixNano: '1700000005000000000',
              attributes: overrides?.topicAttrs ?? [
                { key: 'topic.name', value: { stringValue: 'AI Weekly' } },
                { key: 'weekly_report.article_count', value: { intValue: '5' } },
              ],
              status: { code: 0 },
            },
          ],
        }],
      }],
    }
  }

  it('renders topic sub-rows for a weekly_report.run trace instead of article rows', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce(mockWeeklyReportDetail())

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace01')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace01…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => {
      expect(screen.getByText('AI Weekly')).toBeDefined()
    })
  })

  it('shows "no topics in run" when a weekly_report.run trace has no topic spans', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce({
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{
          spans: [{
            traceId: 'wtrace02',
            spanId: 'root002',
            parentSpanId: '',
            name: 'weekly_report.run',
            startTimeUnixNano: '1700000000000000000',
            endTimeUnixNano: '1700000001000000000',
            attributes: [],
            status: { code: 0 },
          }],
        }],
      }],
    })

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace02')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace02…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => {
      expect(screen.getByText('admin.noTopicsInRun')).toBeDefined()
    })
  })

  it('shows a checkmark status for a successful topic', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce(mockWeeklyReportDetail())

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace01')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace01…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => expect(screen.getByText('AI Weekly')).toBeDefined())
    expect(screen.getByText('✓')).toBeDefined()
    expect(screen.queryByText('✗')).toBeNull()
  })

  it('shows a cross status when the topic span itself errored', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce({
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{
          spans: [
            {
              traceId: 'wtrace03',
              spanId: 'root003',
              parentSpanId: '',
              name: 'weekly_report.run',
              startTimeUnixNano: '1700000000000000000',
              endTimeUnixNano: '1700000008000000000',
              attributes: [],
              status: { code: 0 },
            },
            {
              traceId: 'wtrace03',
              spanId: 'topic003',
              parentSpanId: 'root003',
              name: 'weekly_report.topic',
              startTimeUnixNano: '1700000001000000000',
              endTimeUnixNano: '1700000005000000000',
              attributes: [{ key: 'topic.name', value: { stringValue: 'Errored Topic' } }],
              status: { code: 2 },
            },
          ],
        }],
      }],
    })

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace03')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace03…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => expect(screen.getByText('Errored Topic')).toBeDefined())
    expect(screen.getByText('✗')).toBeDefined()
  })

  it('opens the weekly report topic dialog when a topic row is clicked', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce(mockWeeklyReportDetail())

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace01')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace01…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(screen.getByText('AI Weekly')).toBeDefined())

    fireEvent.click(screen.getByText('view →'))
    await waitFor(() => {
      expect(screen.getByTestId('topic-workflow-dialog')).toBeDefined()
    })
  })

  it('closes the weekly report topic dialog', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce(mockWeeklyReportDetail())

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace01')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace01…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(screen.getByText('AI Weekly')).toBeDefined())
    fireEvent.click(screen.getByText('view →'))
    await waitFor(() => expect(screen.getByTestId('topic-workflow-dialog')).toBeDefined())

    fireEvent.click(screen.getByText('close topic workflow'))
    await waitFor(() => expect(screen.queryByTestId('topic-workflow-dialog')).toBeNull())
  })

  it('opens the topic dialog from the waterfall dialog via onSelectTopic, closing the waterfall', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValue(mockWeeklyReportDetail())

    const external: TempoResponse = { traces: [weeklyReportTrace('wtrace01')] }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('wtrace01…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))
    await waitFor(() => expect(queryTraceById).toHaveBeenCalled())

    fireEvent.click(screen.getByText('wtrace01…'))
    await waitFor(() => expect(screen.getByTestId('waterfall-dialog')).toBeDefined())

    fireEvent.click(screen.getByText('select topic'))
    await waitFor(() => {
      expect(screen.queryByTestId('waterfall-dialog')).toBeNull()
      expect(screen.getByTestId('topic-workflow-dialog')).toBeDefined()
    })
  })

  it('renders article rows (not topic rows) for a non-weekly-report run', async () => {
    const { queryTraceById } = await import('@/lib/api/grafana') as any
    queryTraceById.mockResolvedValueOnce({
      batches: [{
        resource: { attributes: [] },
        scopeSpans: [{
          spans: [
            {
              traceId: 'trace001',
              spanId: 'root001',
              parentSpanId: '',
              name: 'scraper.run',
              startTimeUnixNano: '1700000000000000000',
              endTimeUnixNano: '1700000010000000000',
              attributes: [],
              status: { code: 0 },
            },
          ],
        }],
      }],
    })

    const external: TempoResponse = {
      traces: [{
        traceID: 'trace001',
        rootServiceName: 'backend',
        rootTraceName: 'scraper.run',
        startTimeUnixNano: '1700000000000000000',
        durationMs: 10000,
      }],
    }
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} externalData={external} />)

    await waitFor(() => expect(screen.getByText('trace001…')).toBeDefined())
    fireEvent.click(screen.getByLabelText('Expand'))

    await waitFor(() => {
      expect(screen.getByText('admin.noArticlesInRun')).toBeDefined()
    })
    expect(screen.queryByText('admin.noTopicsInRun')).toBeNull()
  })
})

// ── Self-fetch mode ───────────────────────────────────────────────────────────

describe('TracesTable self-fetch mode', () => {
  it('shows not-configured when queryTraces returns not_configured', async () => {
    const { queryTraces } = await import('@/lib/api/grafana') as any
    queryTraces.mockResolvedValue({ error: 'not_configured' })
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('admin.grafanaNotConfigured')).toBeDefined()
    })
  })

  it('shows error state when queryTraces throws', async () => {
    const { queryTraces } = await import('@/lib/api/grafana') as any
    queryTraces.mockRejectedValue(new Error('network'))
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Traces" refreshInterval={0} />)
    await waitFor(() => {
      expect(screen.getByText('admin.failedToLoadTraces')).toBeDefined()
    })
  })

  it('does not call queryTraces with the placeholder query while externalData is null (pending)', async () => {
    // Regression test: a parent batch hook's initial "not loaded yet" state is
    // externalData={null} (not undefined) precisely so this component can tell
    // "controlled mode, still loading" apart from "no externalData prop at all,
    // please self-fetch" — self-fetching here would send the literal placeholder
    // query="unused" to Grafana Tempo and come back 400 Bad Request.
    const { queryTraces } = await import('@/lib/api/grafana') as any
    const { TracesTable } = await import('@/components/features/monitoring/traces-table')
    render(<TracesTable title="Pending" query="unused" refreshInterval={0} externalData={null} />)
    await waitFor(() => expect(screen.getByText('Pending')).toBeDefined())
    expect(queryTraces).not.toHaveBeenCalled()
  })
})
