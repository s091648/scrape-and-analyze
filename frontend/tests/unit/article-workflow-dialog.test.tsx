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
  StageCard: ({ span, onViewLogs, onToggleCollapse, collapsed, isHighlighted }: any) => (
    <div
      data-testid={`stage-card-${span.spanId}`}
      data-highlighted={String(!!isHighlighted)}
    >
      <span data-testid={`span-name-${span.spanId}`}>{span.name}</span>
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
    name: 'article.pipeline',
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

describe('ArticleWorkflowDialog visibility', () => {
  it('renders nothing when open=false', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    render(
      <ArticleWorkflowDialog
        open={false}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.queryByTestId('dialog')).toBeNull()
  })

  it('renders dialog when open=true', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.getByTestId('dialog')).toBeDefined()
  })

  it('calls onClose when dialog is dismissed', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const onClose = vi.fn()
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={onClose}
        pipelineSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    fireEvent.click(screen.getByTestId('close-dialog'))
    expect(onClose).toHaveBeenCalledOnce()
  })
})

describe('ArticleWorkflowDialog title', () => {
  it('shows article title from stageSpans attributes', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({
      spanId: 'stage1',
      name: 'article.processed.handle',
      attributes: [{ key: 'article.title', value: { stringValue: 'My Great Article' } }],
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(stage)]}
      />
    )
    expect(screen.getByText('My Great Article')).toBeDefined()
  })

  it('falls back to URL when no article.title found', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const pipeline = makeSpan({
      attributes: [{ key: 'article.url', value: { stringValue: 'https://example.com/post' } }],
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={pipeline}
        stageSpans={[]}
      />
    )
    expect(screen.getByText('https://example.com/post')).toBeDefined()
  })

  it('falls back to i18n key when neither title nor URL available', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.getByText('admin.articlePipelineTitle')).toBeDefined()
  })

  it('shows source in subtitle when article.source is present', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const pipeline = makeSpan({
      attributes: [{ key: 'article.source', value: { stringValue: 'techcrunch' } }],
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={pipeline}
        stageSpans={[]}
      />
    )
    expect(screen.getByText('techcrunch')).toBeDefined()
    // The source label is a text node mixed with other content; check textContent
    const dialog = screen.getByTestId('dialog')
    expect(dialog.textContent).toContain('admin.articlePipelineSource')
  })
})

describe('ArticleWorkflowDialog stage rendering', () => {
  it('shows "no stages" message when stageSpans is empty', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[]}
      />
    )
    expect(screen.getByText('admin.articlePipelineNoStages')).toBeDefined()
  })

  it('renders StageCard for each top-level span', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const s1 = makeSpan({ spanId: 'stage1', name: 'article.scraped.handle' })
    const s2 = makeSpan({
      spanId: 'stage2',
      name: 'article.processed.handle',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(s1, 0), makeNode(s2, 0)]}
      />
    )
    expect(screen.getByTestId('stage-card-stage1')).toBeDefined()
    expect(screen.getByTestId('stage-card-stage2')).toBeDefined()
  })

  it('renders child spans nested under parent', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'article.analysis_completed.handle' })
    const child1 = makeSpan({
      spanId: 'child1',
      name: 'article.translate.handle',
      parentSpanId: 'parent1',
    })
    const child2 = makeSpan({
      spanId: 'child2',
      name: 'article.translate.handle',
      parentSpanId: 'parent1',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(child1, 1), makeNode(child2, 1)]}
      />
    )
    expect(screen.getByTestId('stage-card-parent1')).toBeDefined()
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
    expect(screen.getByTestId('stage-card-child2')).toBeDefined()
  })

  it('hides children when parent is collapsed', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'article.analysis_completed.handle' })
    const child = makeSpan({
      spanId: 'child1',
      name: 'article.translate.handle',
      parentSpanId: 'parent1',
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(child, 1)]}
      />
    )
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
    fireEvent.click(screen.getByTestId('toggle-parent1'))
    expect(screen.queryByTestId('stage-card-child1')).toBeNull()
  })

  it('shows children again after expanding a collapsed parent', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const parent = makeSpan({ spanId: 'parent1', name: 'article.analysis_completed.handle' })
    const child = makeSpan({
      spanId: 'child1',
      name: 'article.translate.handle',
      parentSpanId: 'parent1',
    })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(parent, 0), makeNode(child, 1)]}
      />
    )
    fireEvent.click(screen.getByTestId('toggle-parent1'))
    expect(screen.queryByTestId('stage-card-child1')).toBeNull()
    fireEvent.click(screen.getByTestId('toggle-parent1'))
    expect(screen.getByTestId('stage-card-child1')).toBeDefined()
  })

  it('marks highlighted span card', async () => {
    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({ spanId: 'aabbccdd', name: 'article.scraped.handle' })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
        highlightedSpanId="aabbccdd"
      />
    )
    expect(screen.getByTestId('stage-card-aabbccdd').dataset.highlighted).toBe('true')
  })
})

describe('ArticleWorkflowDialog log viewer', () => {
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
              JSON.stringify({ level: 'info', event: 'article_analyzed' }),
            ],
          ],
        }],
      },
    })

    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'article.scraped.handle' })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('view-logs-stage1'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('log-detail')).toBeDefined()
    })
    expect(screen.getByTestId('log-message').textContent).toBe('article_analyzed')
  })

  it('shows "No logs found" fallback when queryLogs returns empty', async () => {
    const { queryLogs } = await import('@/lib/api/grafana') as any
    queryLogs.mockResolvedValueOnce({ status: 'success', data: { result: [] } })

    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'article.scraped.handle' })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
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

    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'article.scraped.handle' })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
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

  it('passes non-JSON log line as message directly', async () => {
    const { queryLogs } = await import('@/lib/api/grafana') as any
    queryLogs.mockResolvedValueOnce({
      status: 'success',
      data: {
        result: [{
          stream: { env: 'local' },
          values: [['1700000000000000000', 'plain text log line']],
        }],
      },
    })

    const { ArticleWorkflowDialog } = await import(
      '@/components/features/monitoring/article-workflow-dialog'
    )
    const stage = makeSpan({ spanId: 'stage1', name: 'article.scraped.handle' })
    render(
      <ArticleWorkflowDialog
        open={true}
        onClose={vi.fn()}
        pipelineSpan={makeSpan()}
        stageSpans={[makeNode(stage, 0)]}
      />
    )

    await act(async () => {
      fireEvent.click(screen.getByTestId('view-logs-stage1'))
    })

    await waitFor(() => {
      expect(screen.getByTestId('log-message').textContent).toBe('plain text log line')
    })
  })
})
