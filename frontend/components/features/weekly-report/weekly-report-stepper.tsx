'use client'
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
  if (!showDots && !onJumpToWeek) return null

  const selected = reports.find(r => r.id === selectedId) ?? null
  // Tutorial highlights a single clickable dot rather than the whole listbox —
  // the first *unselected* one, so it points at something the user can actually switch to.
  const firstUnselectedId = reports.find(r => r.id !== selectedId)?.id

  return (
    <div className="flex h-full flex-col items-center shrink-0 pr-2">
      {showDots && (
        <div role="listbox" aria-label={t('weeklyReport.selectWeek')} className="flex flex-col items-center gap-2">
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
      )}

      {/* Spacer keeps the date picker pinned to the bottom regardless of how many weeks are listed above. */}
      <div className="flex-1" />

      {onJumpToWeek && (
        <div className="pb-1">
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
