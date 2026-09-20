import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { layoutFlamebearer, timelineToCpuSeries } from '@/components/features/monitoring/flame-graph-dialog'
import type { Flamebearer, FlamebearerResponse } from '@/lib/api/grafana'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: any) => (open ? <div data-testid="dialog">{children}</div> : null),
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

// ── FlameGraphDialog rendering ───────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  global.fetch = vi.fn()
})

function mockFetchOnce(body: unknown) {
  ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ json: async () => body })
}

describe('FlameGraphDialog', () => {
  it('renders nothing when closed', async () => {
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={false} onClose={vi.fn()} start={1000} end={1010} />)
    expect(screen.queryByTestId('dialog')).toBeNull()
  })

  it('shows the not-configured message on a 503/not_configured response', async () => {
    mockFetchOnce({ error: 'not_configured' })
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
    await waitFor(() => expect(screen.getByText('admin.profileNotConfigured')).toBeTruthy())
  })

  it('renders frame names from a successful flamebearer response', async () => {
    const body: FlamebearerResponse = {
      version: 1,
      flamebearer: REAL_SAMPLE,
      metadata: { format: 'single', sampleRate: 1_000_000_000, units: 'samples', name: 'cpu' },
    }
    mockFetchOnce(body)
    const { FlameGraphDialog } = await import('@/components/features/monitoring/flame-graph-dialog')
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
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
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
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
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
    await waitFor(() => expect(screen.getByText(/^wide_fn \(/)).toBeTruthy())
    expect(screen.getByText('narrow_fn')).toBeTruthy() // exact match — no "(duration)" suffix
    expect(screen.queryByText(/sliver_fn/)).toBeNull() // rendered, but unlabelled
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
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
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
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
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
    render(<FlameGraphDialog open={true} onClose={vi.fn()} start={1000} end={1010} />)
    await waitFor(() => expect(screen.getByText('admin.profileNoData')).toBeTruthy())
  })
})
