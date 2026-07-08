'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { NativeSelect } from '@/components/ui/native-select'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { fetchLatestWeeklyReport, fetchWeeklyReports, type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportWidgetProps {
  topicId: string | null
  children?: ReactNode
}

const EDGE_MASK: React.CSSProperties = {
  maskImage: 'radial-gradient(ellipse 80% 75% at center, black 35%, transparent 90%)',
  WebkitMaskImage: 'radial-gradient(ellipse 80% 75% at center, black 35%, transparent 90%)',
}

export function WeeklyReportWidget({ topicId, children }: WeeklyReportWidgetProps) {
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!topicId) return
    let cancelled = false
    setLoading(true)
    Promise.allSettled([
      fetchLatestWeeklyReport(topicId),
      fetchWeeklyReports(topicId, 10, 0),
    ]).then(([latestResult, listResult]) => {
      if (cancelled) return
      const list = listResult.status === 'fulfilled' ? listResult.value.items : []
      setReports(list)
      if (latestResult.status === 'fulfilled' && latestResult.value) {
        setSelectedId(latestResult.value.id)
      } else if (list.length > 0) {
        setSelectedId(list[0].id)
      }
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [topicId])

  const selected = reports.find(r => r.id === selectedId) ?? null

  if (!topicId) return null

  const hasCover = !!selected?.cover_image_url

  return (
    <section
      data-testid="weekly-report-widget"
      className="relative overflow-hidden rounded-2xl border border-border isolate"
    >
      {hasCover ? (
        <div
          aria-hidden
          className="absolute inset-0 bg-cover bg-center scale-110"
          style={{
            backgroundImage: `url(${selected!.cover_image_url})`,
            filter: 'blur(8px) saturate(1.05)',
            ...EDGE_MASK,
          }}
        />
      ) : (
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-br from-primary/10 via-muted/40 to-primary/5"
        />
      )}

      <div
        aria-hidden
        className="absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-background/50 to-transparent pointer-events-none"
      />

      <div className="relative p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground/80 uppercase tracking-wide">
            Weekly Report
          </h2>
          {reports.length > 1 && (
            <NativeSelect
              size="sm"
              value={selectedId ?? ''}
              onChange={e => setSelectedId(e.target.value)}
            >
              {reports.map(r => (
                <option key={r.id} value={r.id}>
                  {new Date(r.week_start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </option>
              ))}
            </NativeSelect>
          )}
        </div>

        {loading ? (
          <WeeklyReportSkeleton />
        ) : selected ? (
          <div className="rounded-xl bg-background/85 backdrop-blur-md border border-border/50 shadow-sm p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              {new Date(selected.week_start_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
            </p>
            <h3 className="text-base font-bold leading-snug mb-2">{selected.title}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
              {selected.summary_text}
            </p>
            <p className="text-xs text-muted-foreground mt-2">{selected.article_count} articles</p>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-6 text-center bg-background/70 backdrop-blur-sm">
            <p className="text-sm text-muted-foreground">No report for this week yet.</p>
          </div>
        )}

        {children && (
          <div className="relative -mt-10 z-10 px-2">{children}</div>
        )}
      </div>
    </section>
  )
}
