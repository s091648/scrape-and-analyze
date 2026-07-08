'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { WeeklyReportStepper } from './weekly-report-stepper'
import { WeeklyReportDetailDialog } from './weekly-report-detail-dialog'
import { fetchLatestWeeklyReport, fetchWeeklyReports, type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportWidgetProps {
  topicId: string | null
  children?: ReactNode
}

export function WeeklyReportWidget({ topicId, children }: WeeklyReportWidgetProps) {
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)

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

      <div className="relative h-full overflow-y-auto flex flex-col items-center justify-center gap-4 px-4 py-6">
        {children && (
          <div className="w-[80%] max-w-6xl shrink-0 rounded-2xl bg-white/40 backdrop-blur-sm p-3">{children}</div>
        )}

        <div className="w-[80%] max-w-6xl h-[78%]">
          {loading ? (
            <WeeklyReportSkeleton />
          ) : selected ? (
            <div
              role="button"
              tabIndex={0}
              onClick={() => setDialogOpen(true)}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setDialogOpen(true) }}
              className="flex h-full rounded-2xl bg-white/70 backdrop-blur-md shadow-sm p-4 cursor-pointer overflow-hidden"
              style={{ perspective: 1200 }}
            >
              <WeeklyReportStepper reports={reports} selectedId={selectedId} onSelect={setSelectedId} />

              <div className="flex-1 min-w-0 pl-4 overflow-hidden relative">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={selected.id}
                    initial={{ rotateY: -90, opacity: 0 }}
                    animate={{ rotateY: 0, opacity: 1 }}
                    exit={{ rotateY: 90, opacity: 0 }}
                    transition={{ duration: 0.35, ease: 'easeInOut' }}
                    style={{ transformOrigin: 'left center', backfaceVisibility: 'hidden' }}
                    className="h-full overflow-y-auto"
                  >
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-neutral-600 mb-1">
                      {new Date(selected.week_start_date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </p>
                    <h3 className="text-lg font-bold leading-snug mb-2 text-neutral-900">{selected.title}</h3>
                    <p className="text-sm text-neutral-700 leading-relaxed">
                      {selected.summary_text}
                    </p>
                    <p className="text-xs text-neutral-600 mt-3">{selected.article_count} articles</p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/60 text-center bg-white/70 backdrop-blur-md">
              <p className="text-sm text-neutral-700">No report for this week yet.</p>
            </div>
          )}
        </div>
      </div>

      <WeeklyReportDetailDialog open={dialogOpen} onOpenChange={setDialogOpen} report={selected} />
    </section>
  )
}
