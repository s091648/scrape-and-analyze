import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import type { OtlpSpan } from '@/lib/api/grafana'
import type { SpanNode } from '@/lib/otlp-utils'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (k: string, p?: Record<string, string | number>) =>
      p ? `${k}:${JSON.stringify(p)}` : k,
  }),
}))

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? (
      <div data-testid="dialog">
        {children}
        <button data-testid="close-dialog" onClick={() => onOpenChange?.(false)} />
      </div>
    ) : null,
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h1>{children}</h1>,
}))

vi.mock('@/components/features/monitoring/log-detail-dialog', () => ({
  LogDetailDialog: ({ entry, onClose }: any) =>
    entry ? (
      <div data-testid="log-detail">
        <span data-testid="log-message">{entry.message}</span>
        <button data-testid="close-log" onClick={onClose}>close</button>
      </div>
    ) : null,
}))

vi.mock('@/components/features/monitoring/stage-card', () => ({
  StageCard: ({ span, onViewLogs, onToggleCollapse, collapsed, isHighlighted, labelOverride }: any) => (
    <div
      data-testid={`stage-card-${span.spanId}`}
      data-highlighted={String(!!isHighlighted)}
    >
      <span data-testid={`span-name-${span.spanId}`}>{labelOverride ?? span.name}</span>
      {onViewLogs && (
        <button data-testid={`view-logs-${span.spanId}`} onClick={onViewLogs}>
          View Logs
        </button>
      )}
      {onToggleCollapse && (
        <button data-testid={`toggle-${span.spanId}`} onClick={onToggleCollapse}>
          {collapsed ? 'Expand' : 'Collapse'}
        </button>
      )}
    </div>
  ),
}))

vi.mock('@/lib/api/grafana', () => ({
  queryTracesBatch: vi.fn().mockResolvedValue([]),
  queryLogs: vi.fn().mockResolvedValue({ status: 'success', data: { result: [] } }),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

function makeSpan(overrides: Partial<OtlpSpan> = {}): OtlpSpan {
  return {
    traceId: 'aaaaaaaaaaaaaaaa',
    spanId: 'span1',
    parentSpanId: '',
    name: 'weekly_report.topic',
    startTimeUnixNano: '1700000000000000000',
    endTimeUnixNano: '1700000002000000000',
    attributes: [],
    status: { code: 0 },
    ...overrides,
  }
}

function makeNode(span: OtlpSpan, depth = 0): SpanNode {
  return { span, depth }
}

describe('WeeklyReportTopicDialog visibility', () => {
  it('renders nothing when open=false', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    render(
      <WeeklyReportTopicDialog
        open={false}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.queryByTestId('dialog')).toBeNull()
  })

  it('renders dialog when open=true', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.getByTestId('dialog')).toBeDefined()
  })

  it('calls onClose when dialog is dismissed', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const onClose = vi.fn()
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={onClose}
        topicSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    fireEvent.click(screen.getByTestId('close-dialog'))
    expect(onClose).toHaveBeenCalledOnce()
  })
})

describe('WeeklyReportTopicDialog title/subtitle', () => {
  it('shows topic.name as the dialog title', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const topic = makeSpan({
      attributes: [{ key: 'topic.name', value: { stringValue: 'AI Research Weekly' } }],
    })
    render(
      <WeeklyReportTopicDialog open={true} onClose={vi.fn()} topicSpan={topic} stageSpans={[]} />
    )
    expect(screen.getByText('AI Research Weekly')).toBeDefined()
  })

  it('falls back to i18n key when topic.name is missing', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    render(
      <WeeklyReportTopicDialog open={true} onClose={vi.fn()} topicSpan={makeSpan()} stageSpans={[]} />
    )
    expect(screen.getByText('admin.weeklyReportTopicTitle')).toBeDefined()
  })

  it('shows outcome and article count in the subtitle', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const topic = makeSpan({
      attributes: [
        { key: 'weekly_report.outcome', value: { stringValue: 'success' } },
        { key: 'weekly_report.article_count', value: { intValue: '7' } },
      ],
    })
    render(
      <WeeklyReportTopicDialog open={true} onClose={vi.fn()} topicSpan={topic} stageSpans={[]} />
    )
    const dialog = screen.getByTestId('dialog')
    expect(dialog.textContent).toContain('success')
    expect(dialog.textContent).toContain('7')
  })
})

describe('WeeklyReportTopicDialog stage rendering', () => {
  it('shows "no stages" message when stageSpans is empty', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    render(
      <WeeklyReportTopicDialog open={true} onClose={vi.fn()} topicSpan={makeSpan()} stageSpans={[]} />
    )
    expect(screen.getByText('admin.weeklyReportTopicNoStages')).toBeDefined()
  })

  it('renders StageCard for each top-level span', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const s1 = makeSpan({ spanId: 'stage1', name: 'weekly_report.summarize' })
    const s2 = makeSpan({
      spanId: 'stage2',
      name: 'weekly_report.image',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
    })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(s1, 0), makeNode(s2, 0)]}
      />
    )
    expect(screen.getByTestId('stage-card-stage1')).toBeDefined()
    expect(screen.getByTestId('stage-card-stage2')).toBeDefined()
  })

  it('renders translate/notify child spans nested under parent', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'weekly_report.summarize' })
    const translateChild = makeSpan({
      spanId: 'child1',
      name: 'weekly_report.translate',
      parentSpanId: 'parent1',
      attributes: [{ key: 'translation.language', value: { stringValue: 'zh-TW' } }],
    })
    const notifyChild = makeSpan({
      spanId: 'child2',
      name: 'weekly_report.notify',
      parentSpanId: 'parent1',
      attributes: [{ key: 'notify.channel', value: { stringValue: 'telegram' } }],
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
    })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(translateChild, 1), makeNode(notifyChild, 1)]}
      />
    )
    expect(screen.getByTestId('stage-card-parent1')).toBeDefined()
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
    expect(screen.getByTestId('stage-card-child2')).toBeDefined()
  })

  it('overrides the translate child label with the translation language', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'weekly_report.summarize' })
    const translateChild = makeSpan({
      spanId: 'child1',
      name: 'weekly_report.translate',
      parentSpanId: 'parent1',
      attributes: [{ key: 'translation.language', value: { stringValue: 'zh-TW' } }],
    })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(translateChild, 1)]}
      />
    )
    expect(screen.getByTestId('span-name-child1').textContent).toContain('admin.stageTranslateLabel')
    expect(screen.getByTestId('span-name-child1').textContent).toContain('zh-TW')
  })

  it('overrides the notify child label with the notify channel', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'weekly_report.summarize' })
    const notifyChild = makeSpan({
      spanId: 'child1',
      name: 'weekly_report.notify',
      parentSpanId: 'parent1',
      attributes: [{ key: 'notify.channel', value: { stringValue: 'telegram' } }],
    })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(notifyChild, 1)]}
      />
    )
    expect(screen.getByTestId('span-name-child1').textContent).toContain('admin.weeklyReportNotifyLabel')
    expect(screen.getByTestId('span-name-child1').textContent).toContain('telegram')
  })

  it('hides children when parent is collapsed, and shows them again after expanding', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'weekly_report.summarize' })
    const child = makeSpan({
      spanId: 'child1',
      name: 'weekly_report.translate',
      parentSpanId: 'parent1',
    })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(child, 1)]}
      />
    )
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
    fireEvent.click(screen.getByTestId('toggle-parent1'))
    expect(screen.queryByTestId('stage-card-child1')).toBeNull()
    fireEvent.click(screen.getByTestId('toggle-parent1'))
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
  })

  it('marks highlighted span card', async () => {
    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const stage = makeSpan({ spanId: 'aabbccdd', name: 'weekly_report.summarize' })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
        highlightedSpanId="aabbccdd"
      />
    )
    expect(screen.getByTestId('stage-card-aabbccdd').dataset.highlighted).toBe('true')
  })
})

describe('WeeklyReportTopicDialog log viewer', () => {
  it('shows log detail when queryLogs returns a matching entry', async () => {
    const { queryLogs } = await import('@/lib/api/grafana') as any
    queryLogs.mockResolvedValueOnce({
      status: 'success',
      data: {
        result: [{
          stream: { env: 'production' },
          values: [
            [
              '1700000000000000000',
              JSON.stringify({ level: 'info', event: 'weekly_report_summarized' }),
            ],
          ],
        }],
      },
    })

    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'weekly_report.summarize' })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('view-logs-stage1'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('log-detail')).toBeDefined()
    })
    expect(screen.getByTestId('log-message').textContent).toBe('weekly_report_summarized')
  })

  it('shows "No logs found" fallback when queryLogs returns empty', async () => {
    const { queryLogs } = await import('@/lib/api/grafana') as any
    queryLogs.mockResolvedValueOnce({ status: 'success', data: { result: [] } })

    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'weekly_report.summarize' })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('view-logs-stage1'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('log-detail')).toBeDefined()
    })
    expect(screen.getByTestId('log-message').textContent).toBe('No logs found for this span.')
  })

  it('closes log detail dialog when onClose is called', async () => {
    const { queryLogs } = await import('@/lib/api/grafana') as any
    queryLogs.mockResolvedValueOnce({ status: 'success', data: { result: [] } })

    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'weekly_report.summarize' })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('view-logs-stage1'))
    })
    await waitFor(() => expect(screen.getByTestId('log-detail')).toBeDefined())

    fireEvent.click(screen.getByTestId('close-log'))
    await waitFor(() => expect(screen.queryByTestId('log-detail')).toBeNull())
  })
})

describe('WeeklyReportTopicDialog percentile thresholds', () => {
  it('fetches trace percentiles for each distinct stage span name when opened', async () => {
    const { queryTracesBatch } = await import('@/lib/api/grafana') as any
    queryTracesBatch.mockResolvedValueOnce([])

    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'weekly_report.summarize' })
    render(
      <WeeklyReportTopicDialog
        open={true}
        onClose={vi.fn()}
        topicSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await waitFor(() => {
      expect(queryTracesBatch).toHaveBeenCalledTimes(1)
    })
    const queries = queryTracesBatch.mock.calls[0][0]
    expect(queries).toHaveLength(1)
    expect(queries[0].q).toBe('{ name="weekly_report.summarize" }')
  })

  it('does not fetch percentiles when stageSpans is empty', async () => {
    const { queryTracesBatch } = await import('@/lib/api/grafana') as any

    const { WeeklyReportTopicDialog } = await import(
      '@/components/features/monitoring/weekly-report-topic-dialog'
    )
    render(
      <WeeklyReportTopicDialog open={true} onClose={vi.fn()} topicSpan={makeSpan()} stageSpans={[]} />
    )

    expect(queryTracesBatch).not.toHaveBeenCalled()
  })
})
