'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { NativeSelect } from '@/components/ui/native-select'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { fetchLatestWeeklyReport, fetchWeeklyReports, type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportWidgetProps {
  topicId: string | null
  children?: ReactNode
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
      className="absolute inset-0 overflow-hidden"
    >
      {hasCover ? (
        <div
          aria-hidden
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${selected!.cover_image_url})` }}
        />
      ) : (
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-br from-primary/10 via-muted/40 to-primary/5"
        />
      )}

      <div className="relative h-full overflow-y-auto flex flex-col items-center justify-center gap-6 px-4 py-8">
        {children && (
          <div className="w-full max-w-2xl rounded-2xl bg-white/40 backdrop-blur-sm p-3">{children}</div>
        )}

        <div className="w-full max-w-2xl">
          {loading ? (
            <WeeklyReportSkeleton />
          ) : selected ? (
            <div className="rounded-xl bg-white/70 backdrop-blur-md shadow-sm p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-neutral-600">
                  {new Date(selected.week_start_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                </p>
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
              <h3 className="text-base font-bold leading-snug mb-2 text-neutral-900">{selected.title}</h3>
              <p className="text-xs text-neutral-700 leading-relaxed line-clamp-3">
                {selected.summary_text}
              </p>
              <p className="text-xs text-neutral-600 mt-2">{selected.article_count} articles</p>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-white/60 p-6 text-center bg-white/70 backdrop-blur-md">
              <p className="text-sm text-neutral-700">No report for this week yet.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
