import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { OtlpTraceResponse, OtlpSpan } from '@/lib/api/grafana'
import { SWRTestWrapper } from '@/tests/test-utils/swr'

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
  global.fetch = vi.fn().mockResolvedValue({
    json: async () => ({ error: 'not_configured' }),
  })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
    expect(screen.getByTestId('dialog').textContent).toContain('staging')
  })

  // Both backend/main.py and src/entrypoints/cli/main.py run setup_profiling() as of
  // fix/profiler_imprv — the "View Profile" button shows for either app's trace, not
  // backend-only anymore.
  it('shows the View Profile button for a backend trace', async () => {
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
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.getByText('admin.viewProfile')).toBeTruthy()
  })

  it('shows the View Profile button for a scraper trace', async () => {
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
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.getByText('admin.viewProfile')).toBeTruthy()
  })

  it('hides the View Profile button for a trace from neither profiled app', async () => {
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
          [{ key: 'service.name', value: { stringValue: 'some-other-service' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.queryByText('admin.viewProfile')).toBeNull()
  })

  // Regression test for a real production bug: a 12ms request's [start, end] both
  // BigInt-divide down to the same whole second, producing a zero-width from==until
  // query Pyroscope returns nothing for (confirmed against the real API — see
  // flame-graph-dialog.tsx's git history). The padding must widen the window so
  // start is strictly before end even for a span far under a second.
  it('queries the profile with a padded (non-zero-width) time window for a sub-second span', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    // 12ms span, matching the exact reported bug scenario.
    const span = makeSpan({
      startTimeUnixNano: '1789896395000000000',
      endTimeUnixNano: '1789896395012000000',
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [span],
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByText('admin.viewProfile'))

    // next-auth's real getSession() (unmocked here) fires its own fetch to
    // /api/auth/session first — find the actual profile-query call, not just call #0.
    await vi.waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][]
      expect(calls.some(([u]) => u.includes('/grafana/profile'))).toBe(true)
    })
    const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][]
    const [url] = calls.find(([u]) => u.includes('/grafana/profile'))!
    const params = new URL(url, 'http://localhost').searchParams
    const start = Number(params.get('start'))
    const end = Number(params.get('end'))
    expect(end).toBeGreaterThan(start)
    expect(start).toBe(1789896395 - 10)
    expect(end).toBe(1789896395 + 10)
  })

  it('closes the flame graph dialog when dismissed', async () => {
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
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByText('admin.viewProfile'))
    // FlameGraphDialog renders first in JSX order, so its own Dialog/close-dialog
    // button is the first of the two now mounted (main dialog is always open too).
    expect(screen.getAllByTestId('dialog').length).toBe(2)
    fireEvent.click(screen.getAllByTestId('close-dialog')[0])
    expect(screen.getAllByTestId('dialog').length).toBe(1)
  })

  it('renders without crashing when the trace has no root span', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([])}
      />
    , { wrapper: SWRTestWrapper })
    // No root -> startDate falls back to '—', no View Profile button, no crash.
    expect(screen.getByTestId('dialog')).toBeDefined()
    expect(screen.queryByText('admin.viewProfile')).toBeNull()
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
    const row = screen.getByText('↳ AI News').closest('tr')!
    fireEvent.click(row)
    expect(onSelectTopic).toHaveBeenCalledOnce()
    expect(onSelectTopic.mock.calls[0][0].spanId).toBe('topic001')
  })
})

// fix/profiler_imprv: the CPU-utilization overlay row (always fetched for a profiled trace —
// backend or scraper — not gated behind opening FlameGraphDialog) and the per-span "view
// profile for this span" button (StageCard's onViewProfile), which scopes FlameGraphDialog's
// query to just that span_id instead of the whole padded window.
describe('RunWaterfallDialog CPU overlay + per-span profile', () => {
  function mockFetchProfile(body: unknown) {
    global.fetch = vi.fn((url: unknown) => {
      if (typeof url === 'string' && url.includes('/grafana/profile')) {
        return Promise.resolve({ ok: true, json: async () => body })
      }
      return Promise.resolve({ ok: false, json: async () => ({ error: 'not_configured' }) })
    }) as unknown as typeof fetch
  }

  it('shows the CPU-utilization overlay row once profile timeline data loads', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    // Bucket [1700000000s, 1700000010s) exactly covers makeSpan()'s own [start, end) —
    // lands fully inside the (unpadded) root window, so overlayBars comes back non-empty.
    mockFetchProfile({
      version: 1,
      flamebearer: { names: ['total'], levels: [[0, 1, 0, 0]], numTicks: 1, maxSelf: 0 },
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
      timeline: { startTime: 1700000000, samples: [5_000_000_000], durationDelta: 10, watermarks: null },
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [makeSpan()],
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    await vi.waitFor(() => {
      expect(screen.getByText('admin.waterfallCpuRowLabel')).toBeTruthy()
    })
  })

  it('queries the scraper profile (service=scraper) for a scraper trace', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    mockFetchProfile({
      version: 1,
      flamebearer: { names: ['total'], levels: [[0, 1, 0, 0]], numTicks: 1, maxSelf: 0 },
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
      timeline: { startTime: 1700000000, samples: [5_000_000_000], durationDelta: 10, watermarks: null },
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [makeSpan()],
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    await vi.waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][]
      expect(calls.some(([u]) => u.includes('/grafana/profile') && u.includes('service=scraper'))).toBe(true)
    })
  })

  it('does not show the overlay row when the profile fetch returns no data', async () => {
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
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.queryByText('admin.waterfallCpuRowLabel')).toBeNull()
  })

  it('opens the flame graph scoped to that span_id when its view-profile button is clicked', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root0001', name: 'scraper.run' })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [root],
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer-backend' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByText('scraper.run').closest('tr')!)
    fireEvent.click(screen.getByTitle('admin.viewSpanProfile'))

    await vi.waitFor(() => {
      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][]
      expect(calls.some(([u]) => u.includes('span_id=root0001'))).toBe(true)
    })
  })

  it('shows a per-span view-profile button for a scraper trace too', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root0001', name: 'scraper.run' })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [root],
          [{ key: 'service.name', value: { stringValue: 'scrape-analyzer' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByText('scraper.run').closest('tr')!)
    expect(screen.getByTitle('admin.viewSpanProfile')).toBeTruthy()
  })

  it('does not show a per-span view-profile button for a trace from neither profiled app', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const root = makeSpan({ spanId: 'root0001', name: 'other.run' })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace(
          [root],
          [{ key: 'service.name', value: { stringValue: 'some-other-service' } }]
        )}
      />
    , { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByText('other.run').closest('tr')!)
    expect(screen.queryByTitle('admin.viewSpanProfile')).toBeNull()
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
    // root (depth 0) starts expanded — collapsing it hides its own children.
    expect(screen.getByText('pipeline.fetch')).toBeDefined()
    fireEvent.click(screen.getByLabelText('Collapse'))
    expect(screen.queryByText('pipeline.fetch')).toBeNull()
  })
})

describe('RunWaterfallDialog article status indicator', () => {
  const rootSpan = () => makeSpan({ spanId: 'root001', name: 'scraper.run' })
  const pipelineSpan = () =>
    makeSpan({
      spanId: 'art001',
      parentSpanId: 'root001',
      name: 'article.pipeline',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000002000000000',
      attributes: [{ key: 'article.url', value: { stringValue: 'https://ex.com/a/b' } }],
    })

  it("renders a failed (✗) indicator when article.scraped.handle errored but the pipeline span did not", async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const scraped = makeSpan({
      spanId: 'sc001',
      parentSpanId: 'art001',
      name: 'article.scraped.handle',
      startTimeUnixNano: '1700000001000000000',
      endTimeUnixNano: '1700000001500000000',
      status: { code: 2 },
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([rootSpan(), pipelineSpan(), scraped])}
      />
    , { wrapper: SWRTestWrapper })
    const badge = screen.getByTitle('admin.articleStatusFailed')
    expect(badge.textContent).toBe('✗')
    // row picks up the error styling too
    expect(screen.getByText('↳ a/b').closest('td')?.className).toContain('text-destructive')
  })

  it('renders a partial (▲) indicator when only a later stage failed', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    const analyze = makeSpan({
      spanId: 'an001',
      parentSpanId: 'art001',
      name: 'article.analyze',
      startTimeUnixNano: '1700000001200000000',
      endTimeUnixNano: '1700000001800000000',
      status: { code: 2 },
    })
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([rootSpan(), pipelineSpan(), analyze])}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.getByTitle('admin.articleStatusPartial').textContent).toBe('▲')
    expect(screen.queryByTitle('admin.articleStatusFailed')).toBeNull()
  })

  it('renders no status indicator for a clean pipeline', async () => {
    const { RunWaterfallDialog } = await import(
      '@/components/features/monitoring/run-waterfall-dialog'
    )
    render(
      <RunWaterfallDialog
        open={true}
        onClose={vi.fn()}
        traceId="trace1"
        trace={makeTrace([rootSpan(), pipelineSpan()])}
      />
    , { wrapper: SWRTestWrapper })
    expect(screen.queryByTitle('admin.articleStatusFailed')).toBeNull()
    expect(screen.queryByTitle('admin.articleStatusPartial')).toBeNull()
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
    , { wrapper: SWRTestWrapper })
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
    , { wrapper: SWRTestWrapper })
    const errorBar = container.querySelector('.bg-destructive\\/70')
    expect(errorBar).not.toBeNull()
  })
})
