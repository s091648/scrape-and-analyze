'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { WeeklyReportStepper } from './weekly-report-stepper'
import { fetchLatestWeeklyReport, fetchWeeklyReportByWeek, fetchWeeklyReports, fetchWeeklyReportWeeks, type WeeklyReport } from '@/lib/api/weekly-reports'
import { useI18n } from '@/lib/providers'

function splitParagraphs(text: string): string[] {
  return text.split(/\n+/).map(p => p.trim()).filter(Boolean)
}

function toDateKey(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function mergeReport(prev: WeeklyReport[], report: WeeklyReport): WeeklyReport[] {
  const merged = [...prev.filter(r => r.id !== report.id), report]
  merged.sort((a, b) => b.week_start_date.localeCompare(a.week_start_date))
  return merged
}

interface WeeklyReportWidgetProps {
  topicId: string | null
  /** Deep-link target week (YYYY-MM-DD, any date within the week) — e.g. from a notification CTA. */
  initialWeek?: string | null
  children?: ReactNode
}

export function WeeklyReportWidget({ topicId, initialWeek, children }: WeeklyReportWidgetProps) {
  const { t, locale } = useI18n()
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [availableWeeks, setAvailableWeeks] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!topicId) return
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const [latestResult, listResult] = await Promise.allSettled([
          fetchLatestWeeklyReport(topicId as string, locale),
          fetchWeeklyReports(topicId as string, 10, 0, locale),
        ])
        if (cancelled) return
        const list = listResult.status === 'fulfilled' ? listResult.value.items : []
        setReports(list)

        fetchWeeklyReportWeeks(topicId as string).then(weeks => {
          if (!cancelled) setAvailableWeeks(new Set(weeks.map(w => w.slice(0, 10))))
        })

        if (initialWeek) {
          const match = list.find(r => r.week_start_date.slice(0, 10) === initialWeek)
          const target = match ?? (await fetchWeeklyReportByWeek(topicId as string, initialWeek, locale))
          if (cancelled) return
          if (target) {
            if (!match) setReports(prev => mergeReport(prev, target))
            setSelectedId(target.id)
            return
          }
        }

        if (latestResult.status === 'fulfilled' && latestResult.value) {
          setSelectedId(latestResult.value.id)
        } else if (list.length > 0) {
          setSelectedId(list[0].id)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => { cancelled = true }
  }, [topicId, locale, initialWeek])

  async function handleJumpToWeek(monday: Date) {
    if (!topicId) return
    const weekKey = toDateKey(monday)
    const existing = reports.find(r => r.week_start_date.slice(0, 10) === weekKey)
    if (existing) {
      setSelectedId(existing.id)
      return
    }
    setLoading(true)
    try {
      const fetched = await fetchWeeklyReportByWeek(topicId, weekKey, locale)
      if (fetched) {
        setReports(prev => mergeReport(prev, fetched))
        setSelectedId(fetched.id)
      } else {
        setSelectedId(null)
      }
    } finally {
      setLoading(false)
    }
  }

  const selected = reports.find(r => r.id === selectedId) ?? null

  function isWeekAvailable(monday: Date): boolean {
    const key = toDateKey(monday)
    return availableWeeks.has(key) || reports.some(r => r.week_start_date.slice(0, 10) === key)
  }

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
              className="flex h-full rounded-2xl bg-white/70 backdrop-blur-md shadow-sm pl-3 pr-4 py-4 overflow-hidden"
              style={{ perspective: 1200 }}
            >
              <WeeklyReportStepper
                reports={reports}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onJumpToWeek={handleJumpToWeek}
                isWeekAvailable={isWeekAvailable}
              />

              <div className="flex-1 min-w-0 -my-4 -mr-4 py-4 pr-4 pl-4 rounded-r-2xl bg-white overflow-hidden relative">
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
                      {new Date(selected.week_start_date).toLocaleDateString(locale === 'zh-TW' ? 'zh-TW' : 'en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </p>
                    <h3 className="text-lg font-bold leading-snug mb-3 text-neutral-900">{selected.title}</h3>
                    <div className="space-y-3">
                      {splitParagraphs(selected.summary_text).map((paragraph, i) => (
                        <p key={i} className="text-sm text-neutral-700 leading-relaxed">
                          {paragraph}
                        </p>
                      ))}
                    </div>
                    <p className="text-xs text-neutral-600 mt-4">{t('weeklyReport.articleCount', { count: selected.article_count })}</p>
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/60 text-center bg-white/70 backdrop-blur-md">
              <p className="text-sm text-neutral-700">{t('weeklyReport.noReportYet')}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
