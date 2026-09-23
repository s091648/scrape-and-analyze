'use client'

import { useEffect, useState } from 'react'
import useSWR from 'swr'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
import { queryProfile, type FlamebearerResponse, type Flamebearer, type FlamebearerTimeline } from '@/lib/api/grafana'
import { formatDuration } from '@/lib/otlp-utils'
import { cn } from '@/lib/utils'

interface FlameGraphDialogProps {
  open: boolean
  onClose: () => void
  /** unix seconds — the root span's own [start, end], not a per-child-span window (see
   * backend/routers/grafana.py's /profile docstring for why: CPU sampling needs a wide
   * enough window to be statistically meaningful). */
  start: number
  end: number
  /** Which app's profile to query — "backend" or "scraper" (both are profiled as of
   * fix/profiler_imprv; see queryProfile's own doc comment). Defaults to "backend". */
  service?: 'backend' | 'scraper'
  /** OTel span_id (16 lowercase hex chars) — when given, narrows the flamebearer to CPU
   * samples the matching app's tagging helper tagged with that specific span, instead of
   * every sample in [start, end] (fix/profiler_imprv). `start`/`end` still need to be the
   * padded window (unchanged) — this only narrows which samples within it count. */
  spanId?: string
}

export interface LayoutFrame {
  x: number
  width: number
  self: number
  total: number
  nameIndex: number
  depth: number
}

/**
 * Pyroscope's flamebearer `levels[depth]` is a flat array of 4-number frames
 * [offsetDelta, total, self, nameIndex] — offsetDelta is relative to the END of the
 * previous sibling at that depth, not an absolute x position (confirmed against a real
 * pushed two-sibling sample: a function that ran right after its sibling had
 * offsetDelta=0, not offsetDelta=<sibling's total>). Absolute x is therefore a running
 * sum: x[k] = x[k-1] + total[k-1] + offsetDelta[k].
 */
export function layoutFlamebearer(flamebearer: Flamebearer): LayoutFrame[] {
  const frames: LayoutFrame[] = []
  flamebearer.levels.forEach((level, depth) => {
    let cursor = 0
    for (let i = 0; i < level.length; i += 4) {
      const offsetDelta = level[i]
      const total = level[i + 1]
      const self = level[i + 2]
      const nameIndex = level[i + 3]
      const x = cursor + offsetDelta
      frames.push({ x, width: total, self, total, nameIndex, depth })
      cursor = x + total
    }
  })
  return frames
}

/** Best-effort "package" grouping key for a flamebearer frame name, so every function from
 * the same class/closure renders in the same hue instead of each function getting an
 * independent random color (a full-name hash reads as confetti once a stack is more than a
 * couple of frames deep). Mirrors Grafana's own Flame Graph panel, which colors a single
 * (non-diff) profile "by package" for the same reason: width already encodes "how much
 * time" on this axis, so color's job is "where", not re-encoding time as a heatmap — that's
 * reserved for diff/comparison flame graphs, which this isn't.
 *
 * Verified against a real Grafana Cloud Profiles response (fix/profiler_imprv): pyroscope's
 * Python sampler's frame labels carry NO module/file path and no "(file.py:123)" suffix at
 * all — every name is one of three shapes: a bare function (`sleep`, `list_articles`, no
 * dot at all — nothing to group by, falls back to the whole name as its own key, same as
 * before this scheme existed), `ClassName.method` (`Session.execute`,
 * `RedisCacheGateway.get_or_set` — groups by `ClassName`), or a closure chain
 * (`request_response.<locals>.app` — groups by `request_response.<locals>`, so every
 * closure of the same outer function shares a hue). Splitting on the last `.` handles all
 * three correctly, including nested classes (`TypeEngine.Comparator.operate` groups to
 * `TypeEngine.Comparator`, distinct from `ColumnProperty.Comparator.operate`'s group).
 *
 * Known limitation, inherent to having no module info to disambiguate with: two different
 * libraries' classes that happen to share a name collapse into one group — e.g. `Session`
 * groups SQLAlchemy's Session.execute together with the unrelated `requests` library's
 * Session.post/request/send, and `Span`/`Scope` mix sentry_sdk with opentelemetry. Accepted
 * as-is rather than maintaining a hardcoded per-library class-name map, which would need
 * upkeep every time a dependency's internals change. */
export function frameGroupKey(name: string): string {
  const parts = name.split('.').filter(Boolean)
  return parts.length > 1 ? parts.slice(0, -1).join('.') : name
}

/** Deterministic hue per package key — NOT a fixed/enumerable palette: any package string
 * hashes to *some* point in the full 360° hue range, so there's no finite legend of "every
 * possible color" to print. What buildPackageLegend() below prints instead is the actual
 * per-package colors for whatever's in the currently open flame graph. */
function hueForGroupKey(key: string): number {
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  return hash % 360
}

/** Flat, fixed-S/L representative color for a package — what the legend swatch and every
 * frame's own color used to be before frameColor() below added per-frame heat. Still what
 * the legend uses: a legend entry represents the whole package's identity, not one specific
 * block's weight (the ranking + percentage text next to it already carries that). */
function colorForGroupKey(key: string): string {
  return `hsl(${hueForGroupKey(key)}, 55%, 55%)`
}

// t (0..1, see frameColor) maps to this saturation/lightness range — pale+light at t=0
// ("cold", barely any self time) to vivid+dark at t=1 ("fiery", a real hot spot).
const FRAME_SATURATION_RANGE: [number, number] = [35, 85]
const FRAME_LIGHTNESS_RANGE: [number, number] = [60, 42]
// White label text stops reading clearly above this lightness — switch to dark text instead
// of picking a narrower lightness range that would compress the "pale <-> fiery" contrast
// the whole point of this scheme is to show.
const FRAME_DARK_TEXT_LIGHTNESS_THRESHOLD = 58

/** Per-frame color: hue is the package's (see colorForGroupKey — the same hue the legend
 * swatch for this package uses), but saturation/lightness are modulated by *this specific
 * frame's* own share of total sampled CPU time (self/numTicks) — heavier frames render more
 * saturated and darker ("hotter"), lighter frames closer to a pale, washed-out version of the
 * same hue. This is the middle ground between "hue = package" (this file's prior scheme,
 * which reads as fairly flat/uniform) and a classic flame graph's warm palette (which reads
 * as fire but compresses many distinct packages toward the same hue — see frameGroupKey's own
 * comment for why hue was reserved for package identity): hue still answers "which package",
 * saturation/lightness now also answers "how hot is this exact block", without re-encoding
 * width/total as a second full color axis the way a diff/comparison flame graph's red/blue
 * would.
 *
 * selfRatio is passed through Math.sqrt, not used linearly: most frames in a whole-program
 * capture are a tiny fraction of numTicks, so a linear ramp would leave nearly every block
 * bunched at the pale end — sqrt spreads realistic self-time shares out across the visible
 * range instead. */
export function frameColor(name: string, selfRatio: number): { background: string; textColor: string } {
  const hue = hueForGroupKey(frameGroupKey(name))
  const t = Math.sqrt(Math.max(0, Math.min(1, selfRatio)))
  const saturation = FRAME_SATURATION_RANGE[0] + t * (FRAME_SATURATION_RANGE[1] - FRAME_SATURATION_RANGE[0])
  const lightness = FRAME_LIGHTNESS_RANGE[0] + t * (FRAME_LIGHTNESS_RANGE[1] - FRAME_LIGHTNESS_RANGE[0])
  return {
    background: `hsl(${hue}, ${Math.round(saturation)}%, ${Math.round(lightness)}%)`,
    textColor: lightness > FRAME_DARK_TEXT_LIGHTNESS_THRESHOLD ? '#1a1a1a' : '#ffffff',
  }
}

export interface LegendEntry { key: string; color: string; selfTicks: number }

/** One legend entry per distinct package (frameGroupKey) actually present in `flamebearer`,
 * colored exactly as nameColor() colors that package's frames, ranked by total self time
 * (summed across every frame in that package, not frame count) — the packages actually
 * eating CPU sort first, same ranking principle as the flame graph itself. Reads raw
 * `flamebearer.levels` directly rather than layoutFlamebearer()'s laid-out frames — legend
 * totals don't need x/width, only which package each frame belongs to and its own self
 * ticks. Not capped here — FlameGraphDialog caps how many entries it renders; this returns
 * the full ranked list so the cap stays a presentation concern. */
export function buildPackageLegend(flamebearer: Flamebearer): LegendEntry[] {
  const totals = new Map<string, number>()
  flamebearer.levels.forEach(level => {
    for (let i = 0; i < level.length; i += 4) {
      const self = level[i + 2]
      const key = frameGroupKey(flamebearer.names[level[i + 3]])
      totals.set(key, (totals.get(key) ?? 0) + self)
    }
  })
  return Array.from(totals.entries())
    .map(([key, selfTicks]) => ({ key, color: colorForGroupKey(key), selfTicks }))
    .sort((a, b) => b.selfTicks - a.selfTicks)
}

const ROW_HEIGHT = 22
const AXIS_HEIGHT = 20
// Frames narrower than this are dropped rather than rendered as an unreadable sliver —
// same reasoning as SpanBar's minimum width in run-waterfall-dialog.tsx.
const MIN_WIDTH_PCT = 0.05
// Below this, even the function name alone doesn't fit legibly at 10px — render nothing
// rather than a block with an obviously-clipped one-character label.
const MIN_LABEL_PCT = 1.2
// Below this, the name fits but "name (duration)" doesn't — show just the name.
const MIN_LABEL_WITH_DURATION_PCT = 4

// Legend entries are ranked by self time (buildPackageLegend) and cut off here — a profile
// spanning many modules can have dozens of distinct packages, and a legend that long stops
// being a quick-reference and starts being its own scroll region. The top ones by self time
// are the ones worth naming; everything past this is summarized as "+N more" instead.
const MAX_LEGEND_ENTRIES = 8

// Time-ruler ticks along the top — evenly spaced fractions of the total profiled
// duration, not wall-clock time within the query window (see AxisRuler's own comment).
const AXIS_TICK_FRACTIONS = [0, 0.25, 0.5, 0.75, 1]

const TIMELINE_CHART_HEIGHT = 90

interface TimelinePoint {
  time: string
  cpuPct: number
}

/** Real-timestamp/CPU% series derived from the flamebearer's own `timeline` field — a
 * separate quantity from the flame graph's proportion/depth axes (see FlamebearerTimeline's
 * doc comment). cpuPct is samples[i] / (durationDelta * sampleRate), i.e. the fraction of
 * that bucket's wall-clock width the process was actually on-CPU, expressed as a percentage
 * of one core (a Python process pinned to one core tops out at 100%, not 100% * coreCount). */
export function timelineToCpuSeries(timeline: FlamebearerTimeline, sampleRate: number): TimelinePoint[] {
  const bucketCapacity = timeline.durationDelta * sampleRate
  if (bucketCapacity <= 0) return []
  return timeline.samples.map((value, i) => {
    const ts = timeline.startTime + i * timeline.durationDelta
    return {
      time: new Date(ts * 1000).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      cpuPct: Math.round((value / bucketCapacity) * 1000) / 10,
    }
  })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function renderCpuTooltip(props: any) {
  const { active, payload, label } = props as {
    active?: boolean
    payload?: Array<{ value: number }>
    label?: string
  }
  if (!active || !payload?.length) return null
  return (
    <div
      style={{ transform: 'translateY(calc(-100% - 8px))', pointerEvents: 'none' }}
      className="rounded border border-border bg-background/95 backdrop-blur-sm px-2.5 py-1.5 shadow-sm text-xs"
    >
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p>{payload[0].value}%</p>
    </div>
  )
}

export interface CpuOverlayBar { offsetPct: number; widthPct: number; cpuPct: number }

/** Positions each timeline bucket against [rootStartNs, rootStartNs + rootDurationNs] — the
 * exact same bigint coordinate space RunWaterfallDialog's SpanBar uses for its span rows —
 * so a CPU-utilization strip built from these bars lines up pixel-for-pixel with the span
 * bars beneath it. A bucket entirely outside that window is dropped; one straddling an edge
 * is clamped, mirroring SpanBar's own clamping. Distinct from timelineToCpuSeries above:
 * that one is for FlameGraphDialog's own standalone Recharts panel (categorical time-string
 * x-axis, no alignment concerns); this one is for overlaying onto an existing bigint-ns
 * coordinate space instead. */
export function timelineToOverlayBars(
  timeline: FlamebearerTimeline, sampleRate: number, rootStartNs: bigint, rootDurationNs: bigint,
): CpuOverlayBar[] {
  if (rootDurationNs <= 0n) return []
  const bucketCapacity = timeline.durationDelta * sampleRate
  if (bucketCapacity <= 0) return []
  const rootEndNs = rootStartNs + rootDurationNs
  const bucketDurationNs = BigInt(Math.round(timeline.durationDelta * 1_000_000_000))
  const timelineStartNs = BigInt(Math.round(timeline.startTime * 1_000_000_000))
  const bars: CpuOverlayBar[] = []
  timeline.samples.forEach((value, i) => {
    const bucketStartNs = timelineStartNs + BigInt(i) * bucketDurationNs
    const bucketEndNs = bucketStartNs + bucketDurationNs
    if (bucketEndNs <= rootStartNs || bucketStartNs >= rootEndNs) return
    const clampedStart = bucketStartNs < rootStartNs ? rootStartNs : bucketStartNs
    const clampedEnd = bucketEndNs > rootEndNs ? rootEndNs : bucketEndNs
    const offsetPct = Math.max(0, Number((clampedStart - rootStartNs) * 10000n / rootDurationNs) / 100)
    const widthPct = Math.max(0.3, Number((clampedEnd - clampedStart) * 10000n / rootDurationNs) / 100)
    bars.push({ offsetPct, widthPct, cpuPct: Math.round((value / bucketCapacity) * 1000) / 10 })
  })
  return bars
}

/** Compact heat-strip for RunWaterfallDialog — same visual language as SpanBar (an
 * absolutely-positioned row of blocks), opacity-coded by cpuPct instead of a second chart,
 * so it reads as "part of the waterfall" rather than a separate panel. */
export function CpuUtilizationStrip({ bars }: { bars: CpuOverlayBar[] }) {
  if (bars.length === 0) return null
  return (
    <div className="relative h-3 bg-muted/40 rounded w-full min-w-[80px]">
      {bars.map((bar, i) => (
        <div
          key={i}
          className="absolute h-full bg-amber-500 rounded-[1px]"
          style={{ left: `${bar.offsetPct}%`, width: `${bar.widthPct}%`, opacity: Math.max(0.12, bar.cpuPct / 100) }}
          title={`${bar.cpuPct}% CPU`}
        />
      ))}
    </div>
  )
}

function CpuTimelineChart({ points }: { points: TimelinePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={TIMELINE_CHART_HEIGHT}>
      <BarChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10 }} unit="%" width={36} />
        <Tooltip content={renderCpuTooltip} isAnimationActive={false} />
        <Bar dataKey="cpuPct" fill="hsl(217,91%,60%)" />
      </BarChart>
    </ResponsiveContainer>
  )
}

function AxisRuler({ totalMs }: { totalMs: number }) {
  return (
    <div className="relative border-b border-border text-[10px] text-muted-foreground" style={{ height: AXIS_HEIGHT }}>
      {AXIS_TICK_FRACTIONS.map(frac => (
        <div
          key={frac}
          className="absolute top-0 h-full border-l border-border/60 pl-1"
          style={{ left: `${frac * 100}%` }}
        >
          {formatDuration(totalMs * frac)}
        </div>
      ))}
    </div>
  )
}

export function FlameGraphDialog({ open, onClose, start, end, service, spanId }: FlameGraphDialogProps) {
  const { t } = useI18n()
  // fix/profiler_imprv: (start, end, service, spanId) is an already-resolved, fixed window
  // into the PAST — unlike the Operations/Logs/Traces batch queries elsewhere in this
  // dashboard (which mean "as of now", so the same time-range *selection* resolves to a
  // different absolute [start, end] on every poll and genuinely needs a fresh fetch), the
  // exact same tuple here always answers with the same historical CPU samples. That makes it
  // a good fit for SWR's cache-by-key model where those live-window queries are not:
  // revalidateOnFocus/revalidateIfStale are both off because there is nothing to revalidate
  // — once fetched for a given key, reopening the same span's flame graph should be instant,
  // not a second round trip through the Grafana proxy.
  const key = open ? (['flame-profile', start, end, service ?? 'backend', spanId ?? null] as const) : null
  const { data, isLoading } = useSWR<FlamebearerResponse>(
    key,
    () => queryProfile({ start, end, service, spanId }).catch(() => ({ error: 'fetch_failed' }) as unknown as FlamebearerResponse),
    { revalidateOnFocus: false, revalidateIfStale: false },
  )
  const loading = open && isLoading
  const errorKey = data && 'error' in data ? (data as unknown as { error: string }).error : null
  // Clicking a legend entry (or a frame) toggles this — set, every OTHER package's frames
  // dim instead of the selected one's getting some extra decoration, so the selected
  // package's blocks (which can be scattered across many depths/x-positions, not one
  // contiguous region) pop out across the whole graph at a glance.
  const [selectedPackage, setSelectedPackage] = useState<string | null>(null)

  // Own effect, separate from data fetching (SWR owns that now) — selectedPackage is
  // purely local UI state that must not carry over from a previously viewed flame graph.
  useEffect(() => {
    setSelectedPackage(null)
  }, [open, start, end, service, spanId])

  const flamebearer = data?.flamebearer
  const frames = flamebearer ? layoutFlamebearer(flamebearer) : []
  const numTicks = flamebearer?.numTicks ?? 0
  const sampleRate = data?.metadata?.sampleRate || 1
  const maxDepth = frames.reduce((m, f) => Math.max(m, f.depth), 0)
  const toMs = (ticks: number) => (ticks / sampleRate) * 1000
  const timelinePoints = data?.timeline ? timelineToCpuSeries(data.timeline, sampleRate) : []
  const legend = flamebearer ? buildPackageLegend(flamebearer) : []
  const shownLegend = legend.slice(0, MAX_LEGEND_ENTRIES)
  const hiddenLegendCount = legend.length - shownLegend.length

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-[90vw] sm:max-w-[90vw] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{t('admin.profileDialogTitle')}</DialogTitle>
          {spanId && (
            <p className="text-xs text-muted-foreground font-mono">
              {t('admin.profileScopedToSpan', { id: spanId })}
            </p>
          )}
        </DialogHeader>
        <div className="themed-scrollbar overflow-auto flex-1 min-h-0">
          {loading && (
            <p className="text-sm text-muted-foreground p-4">{t('common.loading')}</p>
          )}
          {!loading && errorKey && (
            <p className="text-sm text-muted-foreground p-4">
              {errorKey === 'not_configured' ? t('admin.profileNotConfigured') : t('admin.profileLoadError')}
            </p>
          )}
          {!loading && !errorKey && numTicks === 0 && (
            <p className="text-sm text-muted-foreground p-4">{t('admin.profileNoData')}</p>
          )}
          {!loading && !errorKey && flamebearer && numTicks > 0 && (
            <>
              {timelinePoints.length > 0 && (
                <div className="px-1 pt-2 pb-1 border-b border-border">
                  <p className="text-xs font-medium text-muted-foreground mb-1">
                    {t('admin.profileTimelineLabel')}
                  </p>
                  <CpuTimelineChart points={timelinePoints} />
                </div>
              )}
              {/* x-axis: fraction of TOTAL PROFILED CPU TIME (numTicks/sampleRate), not
                  wall-clock time within [start, end] — a flame graph's width represents
                  "share of sampled CPU ticks", so this ruler is only meaningful relative
                  to the root's own total, same quantity the root block's own label shows.
                  Real wall-clock time / CPU% lives in the timeline chart above instead. */}
              <AxisRuler totalMs={toMs(numTicks)} />
              <p className="text-[10px] text-muted-foreground px-1 pt-1">
                {t('admin.profileLegend')}
              </p>
              {shownLegend.length > 0 && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 pb-1.5">
                  {shownLegend.map(entry => {
                    const isSelected = selectedPackage === entry.key
                    return (
                      <button
                        key={entry.key}
                        type="button"
                        onClick={() => setSelectedPackage(sel => sel === entry.key ? null : entry.key)}
                        title={entry.key}
                        className={cn(
                          'inline-flex items-center gap-1 text-[10px] rounded px-1 -mx-1 transition-colors cursor-pointer',
                          isSelected ? 'bg-muted text-foreground font-medium' : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        <span className="inline-block w-2.5 h-2.5 rounded-[2px] shrink-0" style={{ backgroundColor: entry.color }} />
                        <span className="max-w-[16rem] truncate">{entry.key}</span>
                        <span className="tabular-nums">{Math.round((entry.selfTicks / numTicks) * 1000) / 10}%</span>
                      </button>
                    )
                  })}
                  {hiddenLegendCount > 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      {t('admin.profileLegendMore', { count: hiddenLegendCount })}
                    </span>
                  )}
                  {selectedPackage && (
                    <button
                      type="button"
                      onClick={() => setSelectedPackage(null)}
                      className="text-[10px] text-muted-foreground hover:text-foreground underline cursor-pointer"
                    >
                      {t('admin.profileLegendClearSelection')}
                    </button>
                  )}
                </div>
              )}
              <div data-testid="flame-graph-frames" className="relative" style={{ height: (maxDepth + 1) * ROW_HEIGHT }}>
                {frames.map((f, i) => {
                  const widthPct = (f.width / numTicks) * 100
                  if (widthPct < MIN_WIDTH_PCT) return null
                  const name = flamebearer.names[f.nameIndex]
                  const durationLabel = formatDuration(toMs(f.total))
                  const label = widthPct < MIN_LABEL_PCT
                    ? ''
                    : widthPct < MIN_LABEL_WITH_DURATION_PCT
                    ? name
                    : `${name} (${durationLabel})`
                  const { background, textColor } = frameColor(name, f.self / numTicks)
                  const groupKey = frameGroupKey(name)
                  const isDimmed = selectedPackage !== null && selectedPackage !== groupKey
                  return (
                    <div
                      key={i}
                      onClick={() => setSelectedPackage(sel => sel === groupKey ? null : groupKey)}
                      className="absolute border border-background overflow-hidden text-[10px] leading-[21px] px-1 whitespace-nowrap cursor-pointer rounded-[2px] transition-opacity"
                      style={{
                        left: `${(f.x / numTicks) * 100}%`,
                        width: `${widthPct}%`,
                        top: f.depth * ROW_HEIGHT,
                        height: ROW_HEIGHT - 1,
                        backgroundColor: background,
                        color: textColor,
                        opacity: isDimmed ? 0.25 : 1,
                      }}
                      title={`${name}\nself: ${formatDuration(toMs(f.self))}\ntotal: ${durationLabel}`}
                    >
                      {label}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
