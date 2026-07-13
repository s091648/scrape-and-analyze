'use client'
import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { type WeeklyReport } from '@/lib/api/weekly-reports'
import { WeekPicker } from '@/components/ui/week-picker'
import { useI18n } from '@/lib/providers'

interface WeeklyReportStepperProps {
  reports: WeeklyReport[]
  selectedId: string | null
  onSelect: (id: string) => void
  onJumpToWeek?: (monday: Date) => void
  isWeekAvailable?: (monday: Date) => boolean
}

export function WeeklyReportStepper({ reports, selectedId, onSelect, onJumpToWeek, isWeekAvailable }: WeeklyReportStepperProps) {
  const { t, locale } = useI18n()
  const showDots = reports.length >= 2
  const listRef = useRef<HTMLDivElement>(null)
  const [isScrollable, setIsScrollable] = useState(false)

  useEffect(() => {
    const el = listRef.current
    if (!el) { setIsScrollable(false); return }
    const check = () => setIsScrollable(el.scrollHeight > el.clientHeight)
    check()
    const observer = new ResizeObserver(check)
    observer.observe(el)
    return () => observer.disconnect()
  }, [reports.length])

  if (!showDots && !onJumpToWeek) return null

  const selected = reports.find(r => r.id === selectedId) ?? null
  // Tutorial highlights a single clickable dot rather than the whole listbox —
  // the first *unselected* one, so it points at something the user can actually switch to.
  const firstUnselectedId = reports.find(r => r.id !== selectedId)?.id

  function scrollToEdge(edge: 'top' | 'bottom') {
    listRef.current?.scrollTo({ top: edge === 'top' ? 0 : listRef.current.scrollHeight, behavior: 'smooth' })
  }

  return (
    <div className="flex h-full flex-col items-center shrink-0 pr-2">
      {/* This flex-1 area keeps the date picker pinned to the bottom regardless of week count —
          when the list overflows it, the listbox scrolls internally instead of pushing/clipping the picker. */}
      <div className="flex min-h-0 flex-1 flex-col items-center">
      {showDots && (
        <>
          {isScrollable && (
            <button
              type="button"
              onClick={() => scrollToEdge('top')}
              aria-label={t('weeklyReport.jumpToNewest')}
              className="shrink-0 cursor-pointer rounded-full p-0.5 text-white/70 hover:bg-white/20 hover:text-white"
            >
              <ChevronUp className="h-3.5 w-3.5" />
            </button>
          )}
          <div ref={listRef} role="listbox" aria-label={t('weeklyReport.selectWeek')} className="flex min-h-0 flex-1 flex-col items-center gap-2 overflow-y-auto">
          {reports.map(r => {
            const isSelected = r.id === selectedId
            return (
              <div
                key={r.id}
                id={r.id === firstUnselectedId ? 'tutorial-target-weekly-weeks' : undefined}
                className={
                  isSelected
                    ? 'relative z-10 translate-x-2 my-1 rounded-l-md bg-white/55 backdrop-blur-md pl-3 pr-5 py-2 shadow-sm'
                    : 'px-3'
                }
              >
                <button
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={e => {
                    e.stopPropagation()
                    onSelect(r.id)
                  }}
                  className="group flex origin-center scale-100 flex-col items-center gap-1.5 cursor-pointer transition-transform duration-150 ease-out hover:scale-105"
                >
                  <span
                    className={`h-2.5 w-2.5 rounded-full transition-colors ${
                      isSelected ? 'bg-neutral-900' : 'bg-white/60 shadow-[0_0_2px_rgba(0,0,0,0.35)] group-hover:bg-white/85'
                    }`}
                  />
                  <span
                    className={`text-[10px] leading-none whitespace-nowrap [writing-mode:vertical-lr] transition-colors ${
                      isSelected ? 'text-neutral-900 font-semibold' : 'text-white/70 drop-shadow-[0_1px_1px_rgba(0,0,0,0.35)]'
                    }`}
                  >
                    {new Date(r.week_start_date).toLocaleDateString(locale === 'zh-TW' ? 'zh-TW' : 'en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </button>
              </div>
            )
          })}
          </div>
          {isScrollable && (
            <button
              type="button"
              onClick={() => scrollToEdge('bottom')}
              aria-label={t('weeklyReport.jumpToOldest')}
              className="shrink-0 cursor-pointer rounded-full p-0.5 text-white/70 hover:bg-white/20 hover:text-white"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
          )}
        </>
      )}
      </div>

      {onJumpToWeek && (
        <div className="pb-1 shrink-0">
          <WeekPicker
            triggerId="tutorial-target-weekly-datepicker"
            value={selected ? new Date(selected.week_start_date) : null}
            onSelectWeek={onJumpToWeek}
            maxDate={new Date()}
            locale={locale}
            compact
            isWeekAvailable={isWeekAvailable}
          />
        </div>
      )}
    </div>
  )
}
