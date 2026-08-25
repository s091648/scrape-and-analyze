import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { OtlpTraceResponse, OtlpSpan } from '@/lib/api/grafana'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({
    t: (k: string, p?: any) => (p ? `${k}:${JSON.stringify(p)}` : k),
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
  DialogTitle: ({ children }: any) => <h1 data-testid="dialog-title">{children}</h1>,
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.resetModules()
})

function makeSpan(overrides: Partial<OtlpSpan> = {}): OtlpSpan {
  return {
    traceId: 'abcdef1234567890',
    spanId: 'root0001',
    parentSpanId: '',
    name: 'scraper.run',
    startTimeUnixNano: '1700000000000000000',
    endTimeUnixNano: '1700000010000000000',
    attributes: [],
    status: { code: 0 },
    ...overrides,
  }
}

function makeTrace(
  spans: OtlpSpan[],
  resourceAttrs: Array<{ key: string; value: { stringValue?: string } }> = []
): OtlpTraceResponse {
  return {
    batches: [{
      resource: { attributes: resourceAttrs },
      scopeSpans: [{ spans }],
    }],
  }
}

describe('RunWaterfallDialog visibility', () => {
  it('renders nothing when open=false', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={false}
        onClose={vi.fn()}
        traceId="abc"
        trace={makeTrace([makeSpan()])}
      />
    )
    expect(screen.queryByTestId('dialog')).toBeNull()
  })

  it('renders dialog when open=true', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="abc"
        trace={makeTrace([makeSpan()])}
      />
    )
    expect(screen.getByTestId('dialog')).toBeDefined()
  })

  it('calls onClose when dialog is dismissed', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const onClose = vi.fn()
    render(
      <RunWaterfallDialog
        open={true}
        onClose={onClose}
        traceId="abc"
        trace={makeTrace([makeSpan()])}
      />
    )
    fireEvent.click(screen.getByTestId('close-dialog'))
    expect(onClose).toHaveBeenCalledOnce()
  })
})

describe('RunWaterfallDialog header', () => {
  it('shows traceId (first 16 chars) in title', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="abcdef1234567890xxxx"
        trace={makeTrace([makeSpan()])}
      />
    )
    const title = screen.getByTestId('dialog-title').textContent ?? ''
    expect(title).toContain('abcdef1234567890')
  })

  it('shows environment from deployment.environment resource attribute', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [makeSpan()],
          [{ key: 'deployment.environment', value: { stringValue: 'production' } }]
        )}
      />
    )
    // Environment is a text node inside a <p> with other content — check container
    expect(screen.getByTestId('dialog').textContent).toContain('production')
  })

  it('shows environment from resource.deployment.environment fallback', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [makeSpan()],
          [{ key: 'resource.deployment.environment', value: { stringValue: 'staging' } }]
        )}
      />
    )
    expect(screen.getByTestId('dialog').textContent).toContain('staging')
  })
})

describe('RunWaterfallDialog waterfall rows', () => {
  it('renders root span in table', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([makeSpan({ name: 'scraper.run', spanId: 'root001' })])}
      />
    )
    expect(screen.getByText('scraper.run')).toBeDefined()
  })

  it('renders child span rows after root', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const child = makeSpan({
      spanId: 'child001',
      parentSpanId: 'root001',
      name: 'pipeline.discover',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, child])}
      />
    )
    expect(screen.getByText('scraper.run')).toBeDefined()
    expect(screen.getByText('pipeline.discover')).toBeDefined()
  })

  it('shows article.pipeline row with truncated URL label', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const article = makeSpan({
      spanId: 'art001',
      parentSpanId: 'root001',
      name: 'article.pipeline',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
      attributes: [
        { key: 'article.url', value: { stringValue: 'https://example.com/section/article-slug' } },
      ],
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, article])}
      />
    )
    // Label shows last 2 path segments: "section/article-slug"
    expect(screen.getByText('↳ section/article-slug')).toBeDefined()
  })

  it('calls onSelectArticle when an article.pipeline row is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const article = makeSpan({
      spanId: 'art001',
      parentSpanId: 'root001',
      name: 'article.pipeline',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
      attributes: [
        { key: 'article.url', value: { stringValue: 'https://ex.com/a/b' } },
      ],
    })
    const onSelectArticle = vi.fn()
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, article])}
        onSelectArticle={onSelectArticle}
      />
    )
    const row = screen.getByText('↳ a/b').closest('tr')!
    fireEvent.click(row)
    expect(onSelectArticle).toHaveBeenCalledOnce()
    expect(onSelectArticle.mock.calls[0][0].spanId).toBe('art001')
  })

  it('does not call onSelectArticle when non-pipeline row is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const onSelectArticle = vi.fn()
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root])}
        onSelectArticle={onSelectArticle}
      />
    )
    fireEvent.click(screen.getByText('scraper.run').closest('tr')!)
    expect(onSelectArticle).not.toHaveBeenCalled()
  })
})

describe('RunWaterfallDialog collapse/expand', () => {
  it('toggles child visibility when expand/collapse button is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const child = makeSpan({
      spanId: 'child001',
      parentSpanId: 'root001',
      name: 'pipeline.fetch',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    const grandchild = makeSpan({
      spanId: 'gc001',
      parentSpanId: 'child001',
      name: 'pipeline.fetch.item',
      startTimeUnixNano: '1700000002000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, child, grandchild])}
      />
    )
    // child (depth 1) has children → initially collapsed
    // grandchild should not be visible initially
    expect(screen.queryByText('fetch.item')).toBeNull()

    // Find and click the expand button on child row
    const expandBtn = screen.getByLabelText('Expand')
    fireEvent.click(expandBtn)

    // After expanding, grandchild should be visible
    expect(screen.getByText('fetch.item')).toBeDefined()
  })

  it('shows collapse button after expanding a collapsed node', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const child = makeSpan({
      spanId: 'child001',
      parentSpanId: 'root001',
      name: 'pipeline.fetch',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    const grandchild = makeSpan({
      spanId: 'gc001',
      parentSpanId: 'child001',
      name: 'pipeline.fetch.item',
      startTimeUnixNano: '1700000002000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, child, grandchild])}
      />
    )
    // Initially: root has Collapse button (has children, not collapsed);
    // child (depth 1, has children) starts collapsed → its Expand button is visible
    const expandBtns = screen.getAllByLabelText('Expand')
    expect(expandBtns.length).toBeGreaterThan(0)
    fireEvent.click(expandBtns[0])
    // After expanding child, there should now be more Collapse buttons than before
    expect(screen.getAllByLabelText('Collapse').length).toBeGreaterThan(0)
  })
})

describe('RunWaterfallDialog topic rows', () => {
  it('calls onSelectTopic when a weekly_report.topic row is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const topic = makeSpan({
      spanId: 'topic001',
      parentSpanId: 'root001',
      name: 'weekly_report.topic',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
      attributes: [{ key: 'topic.name', value: { stringValue: 'AI News' } }],
    })
    const onSelectTopic = vi.fn()
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, topic])}
        onSelectTopic={onSelectTopic}
      />
    )
    const row = screen.getByText('↳ AI News').closest('tr')!
    fireEvent.click(row)
    expect(onSelectTopic).toHaveBeenCalledOnce()
    expect(onSelectTopic.mock.calls[0][0].spanId).toBe('topic001')
  })
})

describe('RunWaterfallDialog span detail preview', () => {
  it('opens a StageCard preview dialog when a non-pipeline/topic row is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root])}
      />
    )
    fireEvent.click(screen.getByText('scraper.run').closest('tr')!)
    // Two dialogs are now mounted — the preview dialog's title is the same span name.
    expect(screen.getAllByTestId('dialog-title').length).toBe(2)
  })

  it('closes the preview dialog when dismissed', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root])}
      />
    )
    fireEvent.click(screen.getByText('scraper.run').closest('tr')!)
    expect(screen.getAllByTestId('dialog-title').length).toBe(2)

    // The first "close-dialog" button belongs to the preview dialog (mounted first).
    fireEvent.click(screen.getAllByTestId('close-dialog')[0])
    expect(screen.getAllByTestId('dialog-title').length).toBe(1)
  })
})

describe('RunWaterfallDialog sibling ordering + collapse-again', () => {
  it('orders sibling rows by start time regardless of input order', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const later = makeSpan({
      spanId: 'later001',
      parentSpanId: 'root001',
      name: 'pipeline.dedup',
      startTimeUnixNano: '1700000005000000000',
      endTimeUnixNano: '1700000006000000000',
    })
    const earlier = makeSpan({
      spanId: 'earlier001',
      parentSpanId: 'root001',
      name: 'pipeline.discover',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
    })
    // Passed in "later, earlier" order — the component must still render discover first.
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, later, earlier])}
      />
    )
    const rows = screen.getAllByRole('row').filter(r => r.querySelector('td'))
    const names = rows.map(r => r.textContent ?? '')
    expect(names.findIndex(n => n.includes('pipeline.discover')))
      .toBeLessThan(names.findIndex(n => n.includes('pipeline.dedup')))
  })

  it('re-collapses an expanded node when its Collapse button is clicked again', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root001', name: 'scraper.run' })
    const child = makeSpan({
      spanId: 'child001',
      parentSpanId: 'root001',
      name: 'pipeline.fetch',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000003000000000',
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root, child])}
      />
    )
    // root (depth 0) starts expanded — collapsing it hides its own children.
    expect(screen.getByText('pipeline.fetch')).toBeDefined()
    fireEvent.click(screen.getByLabelText('Collapse'))
    expect(screen.queryByText('pipeline.fetch')).toBeNull()
  })
})

describe('RunWaterfallDialog SpanBar', () => {
  it('renders span bars in the timeline column', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({
      spanId: 'root001',
      startTimeUnixNano: '1700000000000000000',
      endTimeUnixNano: '1700000010000000000',
    })
    const { container } = render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root])}
      />
    )
    // SpanBar renders a div with absolute-positioned fill
    const bars = container.querySelectorAll('.bg-primary\\/60, .bg-destructive\\/70')
    expect(bars.length).toBeGreaterThan(0)
  })

  it('renders error span bar with destructive color', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({
      spanId: 'root001',
      status: { code: 2 },
    })
    const { container } = render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([root])}
      />
    )
    const errorBar = container.querySelector('.bg-destructive\\/70')
    expect(errorBar).not.toBeNull()
  })
})
