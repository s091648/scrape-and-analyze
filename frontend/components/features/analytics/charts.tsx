'use client'

import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import type { DailyViews, TopicViews } from '@/lib/api/analytics'

const ACCENT = 'hsl(217,91%,60%)'
const AXIS = 'var(--muted-foreground, #888)'

function fmtDay(iso: string): string {
  // "2026-09-10" -> "9/10"
  const [, m, d] = iso.split('-')
  return `${Number(m)}/${Number(d)}`
}

/** Site-wide daily view totals over the selected window. */
export function ViewsTrendChart({ data, height = 220 }: { data: DailyViews[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={AXIS} strokeOpacity={0.2} vertical={false} />
        <XAxis dataKey="day" tickFormatter={fmtDay} stroke={AXIS} fontSize={11} tickMargin={8} minTickGap={24} />
        <YAxis stroke={AXIS} fontSize={11} width={40} allowDecimals={false} />
        <Tooltip
          labelFormatter={(l: string) => fmtDay(l)}
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid var(--border, #ddd)', background: 'var(--background, #fff)' }}
        />
        <Line type="monotone" dataKey="views" stroke={ACCENT} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Per-topic view totals over the selected window, ranked. */
export function TopicBarChart({ data, height = 260 }: { data: TopicViews[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={AXIS} strokeOpacity={0.2} horizontal={false} />
        <XAxis type="number" stroke={AXIS} fontSize={11} allowDecimals={false} />
        <YAxis type="category" dataKey="topic" stroke={AXIS} fontSize={11} width={120} />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid var(--border, #ddd)', background: 'var(--background, #fff)' }}
        />
        <Bar dataKey="views" fill={ACCENT} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Tiny inline trend line for a single article's daily views — no axes, no grid. */
export function Sparkline({ data, width = 120, height = 32 }: { data: DailyViews[]; width?: number; height?: number }) {
  if (!data.length) return <span className="text-muted-foreground text-xs">—</span>
  return (
    <LineChart width={width} height={height} data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
      <Line type="monotone" dataKey="views" stroke={ACCENT} strokeWidth={1.5} dot={false} isAnimationActive={false} />
    </LineChart>
  )
}
