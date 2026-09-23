import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { layoutFlamebearer, timelineToCpuSeries, timelineToOverlayBars, renderCpuTooltip, frameGroupKey, buildPackageLegend, frameColor } from '@/components/features/monitoring/flame-graph-dialog'
import type { Flamebearer, FlamebearerResponse } from '@/lib/api/grafana'
import { SWRTestWrapper } from '@/tests/test-utils/swr'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
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

// ── layoutFlamebearer: the delta-offset resolution, verified against a real pushed
// two-sibling profile (fix/db_imprv spike) — func_a (8.22s) then func_b (3.84s) as
// direct siblings, both with offsetDelta=0 in the raw levels array. If x were absolute
// rather than delta-from-previous-sibling, func_b's raw offset would have been 8220000000,
// not 0 — this fixture is that exact real response. ────────────────────────────────────

const REAL_SAMPLE: Flamebearer = {
  names: ['total', '<module>', 'parent', 'func_b', 'func_a'],
  levels: [
    [0, 12060000000, 0, 0],
    [0, 12060000000, 0, 1],
    [0, 12060000000, 0, 2],
    [0, 8220000000, 8220000000, 4, 0, 3840000000, 3840000000, 3],
  ],
  numTicks: 12060000000,
  maxSelf: 8220000000,
}

// ── frameGroupKey: the color-grouping key nameColor() hashes — same package -> same hue.

// Every name.* case below is a real frame label from a live Grafana Cloud Profiles response
// for this app's backend (fix/profiler_imprv) — pyroscope's Python sampler emits no module/
// file path at all, just these three shapes (see frameGroupKey's own comment).
describe('frameGroupKey', () => {
  it('groups Class.method frames by the class name', () => {
    expect(frameGroupKey('Session.execute')).toBe('Session')
    expect(frameGroupKey('Session._execute_internal')).toBe('Session')
    expect(frameGroupKey('RedisCacheGateway.get_or_set')).toBe('RedisCacheGateway')
    expect(frameGroupKey('RedisCacheGateway._get_or_set')).toBe('RedisCacheGateway')
  })

  it('groups a nested class by its full ClassName.NestedClass path, not just the outer class', () => {
    expect(frameGroupKey('TypeEngine.Comparator.operate')).toBe('TypeEngine.Comparator')
    expect(frameGroupKey('ColumnProperty.Comparator.operate')).toBe('ColumnProperty.Comparator')
  })

  it('groups every closure of the same outer function under one key', () => {
    expect(frameGroupKey('request_response.<locals>.app')).toBe('request_response.<locals>')
    expect(frameGroupKey('request_response.<locals>.app.<locals>.app')).toBe('request_response.<locals>.app.<locals>')
    expect(frameGroupKey('list_tag_groups.<locals>._load')).toBe('list_tag_groups.<locals>')
  })

  it('falls back to the whole name for a bare function with no dot at all', () => {
    expect(frameGroupKey('list_articles')).toBe('list_articles')
    expect(frameGroupKey('record_article_view')).toBe('record_article_view')
    expect(frameGroupKey('<module>')).toBe('<module>')
    expect(frameGroupKey('total')).toBe('total')
  })
})

// ── buildPackageLegend: per-package color legend, ranked by summed self time.

describe('buildPackageLegend', () => {
  const LEGEND_SAMPLE: Flamebearer = {
    names: ['total', 'pkg.foo', 'pkg.bar', 'other.baz'],
    levels: [
      [0, 100, 0, 0],
      [0, 60, 20, 1, 0, 40, 10, 2, 0, 5, 5, 3],
    ],
    numTicks: 100,
    maxSelf: 20,
  }

  it('sums self time across frames that group to the same package', () => {
    const legend = buildPackageLegend(LEGEND_SAMPLE)
    const pkg = legend.find(e => e.key === 'pkg')
    expect(pkg?.selfTicks).toBe(30) // pkg.foo (20) + pkg.bar (10)
  })

  it('ranks entries by self time descending', () => {
    const legend = buildPackageLegend(LEGEND_SAMPLE)
    expect(legend.map(e => e.key)).toEqual(['pkg', 'other', 'total'])
  })

  it('gives every entry a color, and the same key always the same color', () => {
    const legend = buildPackageLegend(LEGEND_SAMPLE)
    const pkg = legend.find(e => e.key === 'pkg')!
    expect(pkg.color).toMatch(/^hsl\(\d+, 55%, 55%\)$/)
    // Re-running on the same data must be deterministic (same hash every time).
    const legend2 = buildPackageLegend(LEGEND_SAMPLE)
    expect(legend2.find(e => e.key === 'pkg')!.color).toBe(pkg.color)
  })
})

// ── frameColor: hue = package (same as buildPackageLegend/colorForGroupKey), but
// saturation/lightness scale with the frame's own self-time share ("heat").

function parseHsl(color: string): { h: number; s: number; l: number } {
  const m = color.match(/^hsl\((\d+), (\d+)%, (\d+)%\)$/)
  if (!m) throw new Error(`not an hsl() string: ${color}`)
  return { h: Number(m[1]), s: Number(m[2]), l: Number(m[3]) }
}

describe('frameColor', () => {
  it('gives two frames in the same package the same hue regardless of self ratio', () => {
    const cold = parseHsl(frameColor('pkg.foo', 0).background)
    const hot = parseHsl(frameColor('pkg.bar', 1).background)
    expect(cold.h).toBe(hot.h) // both group to "pkg"
  })

  it('a hotter frame (higher self ratio) is more saturated and darker than a colder one', () => {
    const cold = parseHsl(frameColor('pkg.foo', 0.01).background)
    const hot = parseHsl(frameColor('pkg.foo', 0.9).background)
    expect(hot.s).toBeGreaterThan(cold.s)
    expect(hot.l).toBeLessThan(cold.l)
  })

  it('clamps out-of-range self ratios instead of producing an invalid color', () => {
    expect(() => parseHsl(frameColor('pkg.foo', -1).background)).not.toThrow()
    expect(() => parseHsl(frameColor('pkg.foo', 5).background)).not.toThrow()
  })

  it('switches to dark text once the background gets light enough to need it', () => {
    const paleFrame = frameColor('pkg.foo', 0)
    const fieryFrame = frameColor('pkg.foo', 1)
    expect(paleFrame.textColor).toBe('#1a1a1a')
    expect(fieryFrame.textColor).toBe('#ffffff')
  })
})

describe('layoutFlamebearer', () => {
  it('resolves single-frame levels to x=0', () => {
    const frames = layoutFlamebearer(REAL_SAMPLE)
    const level0 = frames.filter(f => f.depth === 0)
    expect(level0).toHaveLength(1)
    expect(level0[0]).toMatchObject({ x: 0, width: 12060000000, nameIndex: 0 })
  })

  it('resolves two-sibling level via running sum, not raw offsetDelta', () => {
    const frames = layoutFlamebearer(REAL_SAMPLE)
    const level3 = frames.filter(f => f.depth === 3)
    expect(level3).toHaveLength(2)

    // func_a: first sibling, offsetDelta=0 -> absolute x=0
    expect(level3[0]).toMatchObject({ x: 0, width: 8220000000, self: 8220000000, nameIndex: 4 })

    // func_b: second sibling, raw offsetDelta=0 but starts AFTER func_a ends ->
    // absolute x = func_a's x (0) + func_a's total (8220000000) + own offsetDelta (0)
    expect(level3[1]).toMatchObject({ x: 8220000000, width: 3840000000, self: 3840000000, nameIndex: 3 })
  })

  it('produces one frame per depth for a single-child chain', () => {
    const frames = layoutFlamebearer(REAL_SAMPLE)
    expect(frames).toHaveLength(5) // 1+1+1+2 across depths 0-3
  })
})

// ── timelineToCpuSeries: real-timestamp/CPU% derivation, verified against a real pushed
// burn(5s)/idle(8s)/burn(5s) profile (fix/db_imprv spike) — a bucket covering the first
// burn read back as durationDelta=15, samples[i]=5150000000 (ns), sampleRate=1e9, i.e.
// ~5.15s of the 15s bucket was actually on-CPU -> ~34.3%. ─────────────────────────────

describe('timelineToCpuSeries', () => {
  it('converts ticks-per-bucket into a CPU% of one core', () => {
    const points = timelineToCpuSeries(
      { startTime: 1789914660, samples: [0, 0, 5_150_000_000, 5_030_000_000], durationDelta: 15, watermarks: null },
      1_000_000_000,
    )
    expect(points).toHaveLength(4)
    expect(points[0].cpuPct).toBe(0)
    expect(points[2].cpuPct).toBeCloseTo(34.3, 1)
    expect(points[3].cpuPct).toBeCloseTo(33.5, 1)
  })

  it('returns an empty series for a zero-width bucket instead of dividing by zero', () => {
    const points = timelineToCpuSeries(
      { startTime: 0, samples: [1], durationDelta: 0, watermarks: null },
      1_000_000_000,
    )
    expect(points).toEqual([])
  })
})

// ── timelineToOverlayBars: positions timeline buckets against RunWaterfallDialog's own
// [rootStartNs, rootStartNs+rootDurationNs] bigint coordinate space (fix/profiler_imprv) —
// window [5s, 8s]; bucket 0 ([0s,5s)) ends exactly at rootStart so is dropped entirely,
// bucket 1 ([5s,10s)) straddles the window's own end and is clamped to it, bucket 2
// ([10s,15s)) starts after the window ends so is dropped. ────────────────────────────────

describe('timelineToOverlayBars', () => {
  it('drops buckets outside the window and clamps one straddling its edge', () => {
    const bars = timelineToOverlayBars(
      { startTime: 0, samples: [0, 4_000_000_000, 3_000_000_000], durationDelta: 5, watermarks: null },
      1_000_000_000,
      5_000_000_000n,
      3_000_000_000n,
    )
    expect(bars).toHaveLength(1)
    expect(bars[0].offsetPct).toBeCloseTo(0, 5)
    expect(bars[0].widthPct).toBeCloseTo(100, 5)
    expect(bars[0].cpuPct).toBeCloseTo(80, 5)
  })

  it('returns no bars for a zero-width root window', () => {
    const bars = timelineToOverlayBars(
      { startTime: 0, samples: [1_000_000_000], durationDelta: 5, watermarks: null },
      1_000_000_000,
      0n,
      0n,
    )
    expect(bars).toEqual([])
  })

  it('returns no bars for a zero-width timeline bucket instead of dividing by zero', () => {
    const bars = timelineToOverlayBars(
      { startTime: 0, samples: [1], durationDelta: 0, watermarks: null },
      1_000_000_000,
      0n,
      10_000_000_000n,
    )
    expect(bars).toEqual([])
  })
})

// ── FlameGraphDialog rendering ───────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
})

function mockFetchOnce(body: unknown, ok = true) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok, json: async () => body })
}

describe('FlameGraphDialog', () => {
  it('renders nothing when closed', async () => {
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={false} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    expect(screen.queryByTestId('dialog')).toBeNull()
  })

  it('shows the loading message while the fetch is in flight', async () => {
    let resolveFetch: (value: unknown) => void
    ;(global.fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(resolve => { resolveFetch = resolve })
    )
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('common.loading')).toBeTruthy())
    // Settle the pending fetch before the test ends: lib/api/grafana.ts's authHeaders()
    // caches its own in-flight session-token fetch in a MODULE-level (not per-test)
    // _tokenPromise — a permanently-pending mock here would leave that stuck forever and
    // silently stall every later test's own session-token fetch too, since getSession()'s
    // request goes through this same mocked global.fetch (mirrors why the unmount test
    // below always eventually rejects its own pending promise instead of leaving it
    // hanging).
    resolveFetch!({ ok: true, json: async () => ({ error: 'not_configured' }) })
  })

  it('shows the not-configured message on a 503/not_configured response', async () => {
    mockFetchOnce({ error: 'not_configured' })
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileNotConfigured')).toBeTruthy())
  })

  it('shows the load-error message instead of throwing on a non-2xx response with no error field', async () => {
    mockFetchOnce({ msg: 'bad request' }, false)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileLoadError')).toBeTruthy())
  })

  it('renders frame names from a successful flamebearer response', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    // Wide-enough blocks label as "name (duration)", not just the bare name.
    await waitFor(() => expect(screen.getByText(/^func_a \(/)).toBeTruthy())
    expect(screen.getByText(/^func_b \(/)).toBeTruthy()
  })

  it('shows the axis ruler and legend caption', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileLegend')).toBeTruthy())
    // Axis ruler ticks: 0% and 100% of the root's own total duration (12.06s here).
    // formatDuration(0) is "0 ms" (sub-second branch), not "0 s".
    expect(screen.getByText('0 ms')).toBeTruthy()
    expect(screen.getByText('12.1 s')).toBeTruthy()
  })

  it('labels a narrow-but-visible block with just the name (no duration), and drops an unlabelably narrow one', async () => {
    // Three siblings at depth 0 spanning very different width tiers: 80% (label+duration),
    // 2% (name only, too narrow for "(duration)"), 0.1% (dropped — below MIN_LABEL_PCT but
    // still above MIN_WIDTH_PCT, so it renders as an unlabelled block, not nothing at all).
    const total = 1_000_000_000
    const flamebearer = {
      names: ['total', 'wide_fn', 'narrow_fn', 'sliver_fn'],
      levels: [[0, total, 0, 0], [0, 800_000_000, 800_000_000, 1, 0, 20_000_000, 20_000_000, 2, 0, 1_000_000, 1_000_000, 3]],
      numTicks: total,
      maxSelf: 800_000_000,
    }
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText(/^wide_fn \(/)).toBeTruthy())
    // Scoped to the frames area, not the whole screen — buildPackageLegend's own legend row
    // (fix/profiler_imprv) also prints each package's bare name, which would otherwise
    // collide with this exact-text match on the flame block itself.
    const frames = within(screen.getByTestId('flame-graph-frames'))
    expect(frames.getByText('narrow_fn')).toBeTruthy() // exact match — no "(duration)" suffix
    expect(frames.queryByText(/sliver_fn/)).toBeNull() // rendered, but unlabelled
  })

  it('shows the CPU-over-time chart label when the response includes a timeline', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
      timeline: { startTime: 1789914660, samples: [0, 5_150_000_000], durationDelta: 15, watermarks: null },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileTimelineLabel')).toBeTruthy())
  })

  it('omits the CPU-over-time chart when the response has no timeline', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileLegend')).toBeTruthy())
    expect(screen.queryByText('admin.profileTimelineLabel')).toBeNull()
  })

  it('shows the no-data message when numTicks is 0', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: { names: [], levels: [], numTicks: 0, maxSelf: 0 },
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileNoData')).toBeTruthy())
  })

  it('shows the load-error message when the fetch itself rejects (network error)', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network down'))
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    await waitFor(() => expect(screen.getByText('admin.profileLoadError')).toBeTruthy())
  })

  it('calls onClose when the dialog is dismissed', async () => {
    mockFetchOnce({ error: 'not_configured' })
    const onClose = vi.fn()
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={onClose} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    fireEvent.click(screen.getByTestId('close-dialog'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('does not update state after unmount when a pending fetch later rejects', async () => {
    let reject: (err: unknown) => void
    ;(global.fetch as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise((_resolve, rej) => { reject = rej })
    )
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    const { unmount } = render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    unmount()
    reject!(new Error('network down'))
    await Promise.resolve()
    await Promise.resolve() // no assertion needed — must simply not throw/warn after unmount
  })

  // ── fix/profiler_imprv: SWR caching — (start, end, service, spanId) is an already-resolved
  // window into the past, so the same tuple must be served from cache on a reopen instead of
  // round-tripping through the Grafana proxy again; a genuinely different window must not be.

  function profileFetchCalls() {
    return (global.fetch as ReturnType<typeof vi.fn>).mock.calls
      .filter(([u]) => typeof u === 'string' && u.includes('/grafana/profile'))
  }

  it('serves a reopen of the identical window from the SWR cache instead of refetching', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    const { rerender } = render(
      <FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />,
      { wrapper: SWRTestWrapper },
    )
    await waitFor(() => expect(screen.getByText('admin.profileLegend')).toBeTruthy())
    expect(profileFetchCalls()).toHaveLength(1)

    rerender(<FlameGraphDialog open={false} onClose={vi.fn()} start={1000} end={1010} />)
    rerender(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
    await waitFor(() => expect(screen.getByText('admin.profileLegend')).toBeTruthy())
    expect(profileFetchCalls()).toHaveLength(1) // still just the one call from the first open
  })

  it('fetches again when reopened with a different window (different spanId)', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    const { rerender } = render(
      <FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} spanId="0123456789abcdef" />,
      { wrapper: SWRTestWrapper },
    )
    await waitFor(() => expect(screen.getByText('admin.profileLegend')).toBeTruthy())
    expect(profileFetchCalls()).toHaveLength(1)

    rerender(<FlameGraphDialog open={false} onClose={vi.fn()} start={1000} end={1010} spanId="0123456789abcdef" />)
    rerender(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} spanId="fedcba9876543210" />)
    await waitFor(() => expect(profileFetchCalls()).toHaveLength(2))
  })

  it('drops a frame narrower than the minimum renderable width instead of rendering an unreadable sliver', async () => {
    const total = 1_000_000_000
    const flamebearer = {
      names: ['total', 'visible_fn', 'invisible_fn'],
      levels: [[0, total, 0, 0], [0, 999_900_000, 999_900_000, 1, 0, 100_000, 100_000, 2]],
      numTicks: total,
      maxSelf: 999_900_000,
    }
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    // Scoped to the frames area — buildPackageLegend's own legend row (fix/profiler_imprv)
    // also lists invisible_fn (it's ranked by self time, not rendered width, so a dropped
    // frame can still show up there) with a `title` of its own, which would otherwise
    // collide with these queries.
    const frames = within(await waitFor(() => screen.getByTestId('flame-graph-frames')))
    expect(frames.getByText(/^visible_fn/)).toBeTruthy()
    // invisible_fn is 0.01% of total — below MIN_WIDTH_PCT (0.05%) — dropped entirely.
    expect(frames.queryByTitle(/invisible_fn/)).toBeNull()
  })
})

// ── FlameGraphDialog package highlight (click-to-select) ─────────────────────

describe('FlameGraphDialog package highlight (click-to-select)', () => {
  const HIGHLIGHT_SAMPLE: Flamebearer = {
    names: ['total', 'pkg.foo', 'other.baz'],
    levels: [
      [0, 100, 0, 0],
      [0, 60, 60, 1, 0, 40, 40, 2],
    ],
    numTicks: 100,
    maxSelf: 60,
  }

  function renderHighlightSample() {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: HIGHLIGHT_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
  }

  it('clicking a legend entry dims every frame not in that package', async () => {
    renderHighlightSample()
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    const frames = within(await waitFor(() => screen.getByTestId('flame-graph-frames')))
    const pkgFrame = frames.getByTitle(/^pkg\.foo/)
    const otherFrame = frames.getByTitle(/^other\.baz/)
    expect(pkgFrame.style.opacity).toBe('1')
    expect(otherFrame.style.opacity).toBe('1')

    fireEvent.click(screen.getByText('pkg')) // legend entry's key label

    expect(pkgFrame.style.opacity).toBe('1')
    expect(otherFrame.style.opacity).toBe('0.25')

    // Clicking the same legend entry again toggles the selection back off.
    fireEvent.click(screen.getByText('pkg'))
    expect(otherFrame.style.opacity).toBe('1')
  })

  it('clicking a frame block itself selects its package too, and "clear selection" resets it', async () => {
    renderHighlightSample()
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />, { wrapper: SWRTestWrapper })
    const frames = within(await waitFor(() => screen.getByTestId('flame-graph-frames')))
    const pkgFrame = frames.getByTitle(/^pkg\.foo/)
    const otherFrame = frames.getByTitle(/^other\.baz/)

    fireEvent.click(pkgFrame)
    expect(otherFrame.style.opacity).toBe('0.25')
    expect(screen.getByText('admin.profileLegendClearSelection')).toBeTruthy()

    fireEvent.click(screen.getByText('admin.profileLegendClearSelection'))
    expect(otherFrame.style.opacity).toBe('1')
    expect(screen.queryByText('admin.profileLegendClearSelection')).toBeNull()
  })
})

// ── renderCpuTooltip ─────────────────────────────────────────────────────────

describe('renderCpuTooltip', () => {
  it('renders nothing when inactive', () => {
    expect(renderCpuTooltip({ active: false, payload: [{ value: 42 }], label: '10:00:00' })).toBeNull()
  })

  it('renders nothing when there is no payload', () => {
    expect(renderCpuTooltip({ active: true, payload: [], label: '10:00:00' })).toBeNull()
  })

  it('renders the label and CPU% when active with a payload', () => {
    const { container } = render(
      <>{renderCpuTooltip({ active: true, payload: [{ value: 42 }], label: '10:00:00' })}</>
    , { wrapper: SWRTestWrapper })
    expect(container.textContent).toContain('10:00:00')
    expect(container.textContent).toContain('42%')
  })
})
