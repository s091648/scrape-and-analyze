'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft, ChevronRight, Sparkles } from 'lucide-react'
import { WeeklyReportSkeleton } from './weekly-report-skeleton'
import { WeeklyReportStepper } from './weekly-report-stepper'
import { fetchLatestWeeklyReport, fetchWeeklyReportByWeek, fetchWeeklyReports, fetchWeeklyReportWeeks, type WeeklyReport } from '@/lib/api/weekly-reports'
import { useI18n, usePinnedArticle } from '@/lib/providers'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { CitedContent } from '@/components/features/chat/cited-content'

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
  const { pinArticles, removePinnedArticle, areAllPinned } = usePinnedArticle()
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [availableWeeks, setAvailableWeeks] = useState<Set<string>>(new Set())
  const [collapsed, setCollapsed] = useState(false)

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

  function handleTogglePinReport() {
    if (!selected || selected.sources.length === 0) return
    const ids = selected.sources.map(s => s.id)
    if (areAllPinned(ids)) {
      ids.forEach(id => removePinnedArticle(id))
    } else {
      pinArticles(selected.sources.map(s => ({ id: s.id, title: s.title ?? s.url, tags: [] })))
    }
  }

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

      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setCollapsed(v => !v)}
              aria-label={t(collapsed ? 'weeklyReport.expand' : 'weeklyReport.collapse')}
              aria-pressed={collapsed}
              className="absolute right-3 top-1/2 z-20 -translate-y-1/2 flex size-8 cursor-pointer items-center justify-center rounded-full bg-white/70 text-neutral-800 shadow-sm backdrop-blur-md transition hover:bg-white/90"
            >
              {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
            </button>
          </TooltipTrigger>
          <TooltipContent>{t(collapsed ? 'weeklyReport.expand' : 'weeklyReport.collapse')}</TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <motion.div
        animate={collapsed ? { opacity: 0, x: 24 } : { opacity: 1, x: 0 }}
        transition={{ duration: 0.25, ease: 'easeInOut' }}
        style={{ pointerEvents: collapsed ? 'none' : 'auto' }}
        className="relative h-full overflow-y-auto flex flex-col items-center justify-center gap-4 px-4 py-6"
      >
        {children && (
          <div className="w-[80%] max-w-6xl shrink-0 rounded-2xl bg-white/40 backdrop-blur-sm p-3">{children}</div>
        )}

        <div className="w-[80%] max-w-6xl h-[78%]">
          {loading ? (
            <WeeklyReportSkeleton />
          ) : selected ? (
            <div
              className="flex h-full rounded-2xl bg-white/10 backdrop-blur-[2px] shadow-sm pl-3 pr-4 py-4 overflow-hidden"
              style={{ perspective: 1200 }}
            >
              <WeeklyReportStepper
                reports={reports}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onJumpToWeek={handleJumpToWeek}
                isWeekAvailable={isWeekAvailable}
              />

              <div className="flex-1 min-w-0 -my-4 -mr-4 py-4 pr-4 pl-4 rounded-r-2xl bg-white/55 backdrop-blur-md overflow-hidden relative">
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
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <h3 className="text-lg font-bold leading-snug text-neutral-900">{selected.title}</h3>
                      {selected.sources.length > 0 && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <button
                                type="button"
                                onClick={handleTogglePinReport}
                                aria-label={t(areAllPinned(selected.sources.map(s => s.id)) ? 'weeklyReport.unpinReport' : 'weeklyReport.pinReport')}
                                className={`shrink-0 mt-0.5 inline-flex items-center justify-center h-6 w-6 rounded-full cursor-pointer transition-colors ${
                                  areAllPinned(selected.sources.map(s => s.id))
                                    ? 'bg-purple-100 dark:bg-purple-900/40'
                                    : 'hover:bg-purple-100 dark:hover:bg-purple-900/40'
                                }`}
                              >
                                <Sparkles className={`h-3.5 w-3.5 transition-colors ${
                                  areAllPinned(selected.sources.map(s => s.id)) ? 'text-purple-600 dark:text-purple-400' : 'text-purple-400'
                                }`} />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent>{t(areAllPinned(selected.sources.map(s => s.id)) ? 'weeklyReport.unpinReport' : 'weeklyReport.pinReport')}</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </div>
                    <div className="text-sm text-neutral-700 leading-relaxed">
                      <CitedContent text={selected.summary_text} sources={selected.sources} />
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
      </motion.div>
    </section>
  )
}
