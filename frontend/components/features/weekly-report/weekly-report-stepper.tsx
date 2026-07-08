'use client'
import { type WeeklyReport } from '@/lib/api/weekly-reports'

interface WeeklyReportStepperProps {
  reports: WeeklyReport[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function WeeklyReportStepper({ reports, selectedId, onSelect }: WeeklyReportStepperProps) {
  if (reports.length < 2) return null

  return (
    <div
      role="listbox"
      aria-label="Select report week"
      className="flex flex-col items-center gap-1 pr-4 border-r border-neutral-900/10 shrink-0"
    >
      {reports.map(r => {
        const isSelected = r.id === selectedId
        return (
          <button
            key={r.id}
            type="button"
            role="option"
            aria-selected={isSelected}
            onClick={e => {
              e.stopPropagation()
              onSelect(r.id)
            }}
            className="group flex flex-col items-center gap-1 py-1.5 px-1 cursor-pointer"
          >
            <span
              className={`h-2.5 w-2.5 rounded-full transition-colors ${
                isSelected ? 'bg-neutral-900' : 'bg-neutral-900/25 group-hover:bg-neutral-900/50'
              }`}
            />
            <span
              className={`text-[10px] leading-none whitespace-nowrap [writing-mode:vertical-rl] transition-colors ${
                isSelected ? 'text-neutral-900 font-semibold' : 'text-neutral-600'
              }`}
            >
              {new Date(r.week_start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          </button>
        )
      })}
    </div>
  )
}
