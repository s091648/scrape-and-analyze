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

  return (
    <div className="flex h-full flex-col items-center shrink-0 pr-2">
      {showDots && (
        <div role="listbox" aria-label={t('weeklyReport.selectWeek')} className="flex flex-col items-center gap-2">
          {reports.map(r => {
            const isSelected = r.id === selectedId
            return (
              <div
                key={r.id}
                className={
                  isSelected
                    ? 'relative z-10 translate-x-2.5 my-1 rounded-l-md bg-white pl-3 pr-5 py-2 shadow-[-2px_2px_6px_-2px_rgba(0,0,0,0.15)]'
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
                      isSelected ? 'bg-neutral-900' : 'bg-neutral-900/25 group-hover:bg-neutral-900/50'
                    }`}
                  />
                  <span
                    className={`text-[10px] leading-none whitespace-nowrap [writing-mode:vertical-lr] transition-colors ${
                      isSelected ? 'text-neutral-900 font-semibold' : 'text-neutral-600'
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
