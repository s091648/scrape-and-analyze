'use client'

import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
import { queryProfile, type FlamebearerResponse, type Flamebearer, type FlamebearerTimeline } from '@/lib/api/grafana'
import { formatDuration } from '@/lib/otlp-utils'

interface FlameGraphDialogProps {
  open: boolean
  onClose: () => void
  /** unix seconds — the root span's own [start, end], not a per-child-span window (see
   * backend/routers/grafana.py's /profile docstring for why: CPU sampling needs a wide
   * enough window to be statistically meaningful). */
  start: number
  end: number
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

/** Deterministic hue per function name — the same function always gets the same color
 * across renders, without maintaining a fixed palette for open-ended function names
 * (unlike e.g. CLIENT_TYPE_CHART_COLORS, whose value set is small and known upfront). */
function nameColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  return `hsl(${hash % 360}, 55%, 55%)`
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
function renderCpuTooltip(props: any) {
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

export function FlameGraphDialog({ open, onClose, start, end }: FlameGraphDialogProps) {
  const { t } = useI18n()
  const [data, setData] = useState<FlamebearerResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [errorKey, setErrorKey] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    setErrorKey(null)
    setData(null)
    queryProfile({ start, end })
      .then(res => {
        if (cancelled) return
        if ('error' in res) {
          setErrorKey((res as unknown as { error: string }).error)
        } else {
          setData(res)
        }
      })
      .catch(() => { if (!cancelled) setErrorKey('fetch_failed') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [open, start, end])

  const flamebearer = data?.flamebearer
  const frames = flamebearer ? layoutFlamebearer(flamebearer) : []
  const numTicks = flamebearer?.numTicks ?? 0
  const sampleRate = data?.metadata?.sampleRate || 1
  const maxDepth = frames.reduce((m, f) => Math.max(m, f.depth), 0)
  const toMs = (ticks: number) => (ticks / sampleRate) * 1000
  const timelinePoints = data?.timeline ? timelineToCpuSeries(data.timeline, sampleRate) : []

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="max-w-[90vw] sm:max-w-[90vw] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>{t('admin.profileDialogTitle')}</DialogTitle>
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
              <p className="text-[10px] text-muted-foreground px-1 py-1">
                {t('admin.profileLegend')}
              </p>
              <div className="relative" style={{ height: (maxDepth + 1) * ROW_HEIGHT }}>
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
                  return (
                    <div
                      key={i}
                      className="absolute border border-background overflow-hidden text-[10px] leading-[21px] px-1 text-white whitespace-nowrap cursor-default rounded-[2px]"
                      style={{
                        left: `${(f.x / numTicks) * 100}%`,
                        width: `${widthPct}%`,
                        top: f.depth * ROW_HEIGHT,
                        height: ROW_HEIGHT - 1,
                        backgroundColor: nameColor(name),
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
