'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { DndContext, type DragEndEvent } from '@dnd-kit/core'
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, MessageSquare, Newspaper, Sparkles } from 'lucide-react'
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

/** Short date label shared by the stepper's week dots and the group pin pill's label. */
function formatShortDate(dateStr: string, locale: string): string {
  return new Date(dateStr).toLocaleDateString(locale === 'zh-TW' ? 'zh-TW' : 'en-US', { month: 'short', day: 'numeric' })
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
  /** Render-prop rather than a plain node: the chat child needs to tell this widget when a
   * message is sent (to switch from the stacked layout into report/chat card-swap mode and
   * jump to the chat card), and a plain ReactNode has no channel to call back up. */
  children?: (props: { onSend: () => void }) => ReactNode
}

export function WeeklyReportWidget({ topicId, initialWeek, children }: WeeklyReportWidgetProps) {
  const { t, locale } = useI18n()
  const { pinArticles, pinGroup, removeGroup, areAllPinned } = usePinnedArticle()
  const [reports, setReports] = useState<WeeklyReport[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [availableWeeks, setAvailableWeeks] = useState<Set<string>>(new Set())
  const [collapsed, setCollapsed] = useState(false)
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  // Card-swap mode only kicks in once the chat has an actual conversation — before that,
  // the report and chat children keep stacking vertically as they always have (small input
  // bar, no overflow risk yet).
  const [hasConversation, setHasConversation] = useState(false)
  const [activeCard, setActiveCard] = useState<'report' | 'chat'>('report')

  function handleMessageSent() {
    setHasConversation(true)
    setActiveCard('chat')
  }

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

  useEffect(() => {
    setSourcesExpanded(false)
  }, [selectedId])

  function handleTogglePinReport() {
    if (!selected || selected.sources.length === 0) return
    const ids = selected.sources.map(s => s.id)
    if (areAllPinned(ids)) {
      removeGroup(selected.id)
    } else {
      pinGroup({
        id: selected.id,
        dateLabel: formatShortDate(selected.week_start_date, locale),
        articles: selected.sources.map(s => ({ id: s.id, title: s.title ?? s.url, tags: [] })),
      })
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    if (event.over?.id !== 'chat-input-dropzone') return
    const article = event.active.data.current?.article as { id: string; title: string } | undefined
    if (article) pinArticles([article])
  }

  function isWeekAvailable(monday: Date): boolean {
    const key = toDateKey(monday)
    return availableWeeks.has(key) || reports.some(r => r.week_start_date.slice(0, 10) === key)
  }

  if (!topicId) return null

  const hasCover = !!selected?.cover_image_url

  const reportCardBody = loading ? (
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
              <CitedContent
                text={selected.summary_text}
                sources={selected.sources}
                showSourceList={sourcesExpanded}
                draggableSources
                onRefClick={() => setSourcesExpanded(true)}
                extraContent={
                  <button
                    type="button"
                    onClick={() => setSourcesExpanded(v => !v)}
                    className="mt-4 flex cursor-pointer items-center gap-1 text-xs text-neutral-600 hover:text-neutral-900"
                  >
                    {sourcesExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                    {t('weeklyReport.articleCount', { count: selected.article_count })}
                  </button>
                }
              />
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  ) : (
    <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/60 text-center bg-white/70 backdrop-blur-md">
      <p className="text-sm text-neutral-700">{t('weeklyReport.noReportYet')}</p>
    </div>
  )

  return (
    <DndContext onDragEnd={handleDragEnd}>
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

      <div className="absolute right-3 top-1/2 z-20 -translate-y-1/2 flex flex-col gap-2">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={() => setCollapsed(v => !v)}
                aria-label={t(collapsed ? 'weeklyReport.expand' : 'weeklyReport.collapse')}
                aria-pressed={collapsed}
                className="flex size-8 cursor-pointer items-center justify-center rounded-full bg-white/70 text-neutral-800 shadow-sm backdrop-blur-md transition hover:bg-white/90"
              >
                {collapsed ? <ChevronRight className="size-4" /> : <ChevronLeft className="size-4" />}
              </button>
            </TooltipTrigger>
            <TooltipContent>{t(collapsed ? 'weeklyReport.expand' : 'weeklyReport.collapse')}</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        {hasConversation && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => setActiveCard(c => (c === 'chat' ? 'report' : 'chat'))}
                  aria-label={t(activeCard === 'chat' ? 'weeklyReport.switchToReport' : 'weeklyReport.switchToChat')}
                  className="flex size-8 cursor-pointer items-center justify-center rounded-full bg-purple-100 text-purple-600 shadow-sm backdrop-blur-md transition hover:bg-purple-200 dark:bg-purple-900/40 dark:text-purple-300 dark:hover:bg-purple-800/60"
                >
                  {activeCard === 'chat' ? <Newspaper className="size-4" /> : <MessageSquare className="size-4" />}
                </button>
              </TooltipTrigger>
              <TooltipContent>{t(activeCard === 'chat' ? 'weeklyReport.switchToReport' : 'weeklyReport.switchToChat')}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>

      <motion.div
        animate={collapsed ? { opacity: 0, x: 24 } : { opacity: 1, x: 0 }}
        transition={{ duration: 0.25, ease: 'easeInOut' }}
        style={{ pointerEvents: collapsed ? 'none' : 'auto' }}
        className="relative h-full overflow-y-auto flex flex-col items-center justify-center gap-4 px-4 py-6"
      >
        {hasConversation ? (
          // Once the chat has a real conversation, the report and chat no longer stack
          // (that overflows vertically) — they swap in the same slot via the header button.
          <div className="relative w-[80%] max-w-6xl h-[78%]">
            <AnimatePresence mode="wait">
              {activeCard === 'chat' ? (
                <motion.div
                  key="chat-card"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="h-full overflow-hidden rounded-2xl bg-white/40 backdrop-blur-sm p-3"
                >
                  {children?.({ onSend: handleMessageSent })}
                </motion.div>
              ) : (
                <motion.div
                  key="report-card"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="h-full"
                >
                  {reportCardBody}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ) : (
          <>
            {children && (
              <div className="w-[80%] max-w-6xl shrink-0 rounded-2xl bg-white/40 backdrop-blur-sm p-3">
                {children({ onSend: handleMessageSent })}
              </div>
            )}

            <div className="w-[80%] max-w-6xl h-[78%]">
              {reportCardBody}
            </div>
          </>
        )}
      </motion.div>
    </section>
    </DndContext>
  )
}
