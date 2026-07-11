'use client'

import { useState } from 'react'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d)
  r.setDate(r.getDate() + n)
  return r
}

function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1)
}

/** Monday of the week containing *d* (week starts Monday, matching the backend's week normalization). */
function mondayOf(d: Date): Date {
  const dayIndex = (d.getDay() + 6) % 7 // Mon=0 ... Sun=6
  return addDays(new Date(d.getFullYear(), d.getMonth(), d.getDate()), -dayIndex)
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
}

/** Fixed 6-row grid of Monday-start weeks covering *viewMonth*, including leading/trailing days. */
function buildWeeks(viewMonth: Date): Date[][] {
  const gridStart = mondayOf(startOfMonth(viewMonth))
  const weeks: Date[][] = []
  let cursor = gridStart
  for (let w = 0; w < 6; w++) {
    const week: Date[] = []
    for (let d = 0; d < 7; d++) {
      week.push(cursor)
      cursor = addDays(cursor, 1)
    }
    weeks.push(week)
  }
  return weeks
}

interface WeekPickerProps {
  /** Any date within the currently selected week; internally normalized to that week's Monday. */
  value: Date | null
  onSelectWeek: (monday: Date) => void
  minDate?: Date
  maxDate?: Date
  /** Drives month/weekday label formatting. */
  locale?: string
  className?: string
  /** Icon-only trigger (no date/label text) — for narrow layouts. */
  compact?: boolean
  /** When provided, weeks for which this returns false are disabled (e.g. no report exists for that week yet). */
  isWeekAvailable?: (monday: Date) => boolean
}

export function WeekPicker({
  value,
  onSelectWeek,
  minDate,
  maxDate,
  locale = 'en',
  className,
  compact = false,
  isWeekAvailable,
}: WeekPickerProps) {
  const [open, setOpen] = useState(false)
  const [viewMonth, setViewMonth] = useState(() => startOfMonth(value ?? new Date()))
  const [hoveredRow, setHoveredRow] = useState<number | null>(null)

  const localeTag = locale === 'zh-TW' ? 'zh-TW' : 'en-US'
  const weeks = buildWeeks(viewMonth)
  const monthLabel = viewMonth.toLocaleDateString(localeTag, { month: 'long', year: 'numeric' })
  const weekdayLabels = Array.from({ length: 7 }, (_, i) =>
    addDays(mondayOf(new Date()), i).toLocaleDateString(localeTag, { weekday: 'narrow' })
  )
  const selectedMonday = value ? mondayOf(value) : null
  const triggerLabel = selectedMonday
    ? selectedMonday.toLocaleDateString(localeTag, { month: 'short', day: 'numeric' })
    : locale === 'zh-TW' ? '跳到某週' : 'Jump to week'

  function isRowDisabled(week: Date[]): boolean {
    const monday = week[0]
    const sunday = week[6]
    if (minDate && sunday < mondayOf(minDate)) return true
    if (maxDate && monday > maxDate) return true
    if (isWeekAvailable && !isWeekAvailable(monday)) return true
    return false
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {compact ? (
          <button
            type="button"
            aria-label={triggerLabel}
            title={triggerLabel}
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded-full border border-border bg-background text-neutral-600 transition-colors hover:bg-muted cursor-pointer',
              className
            )}
          >
            <Calendar className="size-4" />
          </button>
        ) : (
          <button
            type="button"
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-neutral-700 transition-colors hover:bg-muted cursor-pointer',
              className
            )}
          >
            <Calendar className="size-3.5" />
            {triggerLabel}
          </button>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-64 p-3" align="center" side="top">
        <div className="mb-2 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setViewMonth(prev => addMonths(prev, -1))}
            className="rounded p-1 hover:bg-muted cursor-pointer"
            aria-label="Previous month"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="text-xs font-semibold text-neutral-800">{monthLabel}</span>
          <button
            type="button"
            onClick={() => setViewMonth(prev => addMonths(prev, 1))}
            className="rounded p-1 hover:bg-muted cursor-pointer"
            aria-label="Next month"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>

        <div className="grid grid-cols-7 gap-y-0.5 text-center">
          {weekdayLabels.map((w, i) => (
            <span key={i} className="text-[10px] font-medium text-muted-foreground">
              {w}
            </span>
          ))}
        </div>

        <div role="listbox" aria-label={locale === 'zh-TW' ? '選擇週次' : 'Select week'} className="space-y-0.5">
          {weeks.map((week, rowIdx) => {
            const monday = week[0]
            const isSelectedRow = selectedMonday ? isSameDay(monday, selectedMonday) : false
            const disabled = isRowDisabled(week)
            return (
              <div
                key={rowIdx}
                role="option"
                aria-selected={isSelectedRow}
                aria-disabled={disabled}
                onMouseEnter={() => setHoveredRow(rowIdx)}
                onMouseLeave={() => setHoveredRow(prev => (prev === rowIdx ? null : prev))}
                onClick={() => {
                  if (disabled) return
                  onSelectWeek(monday)
                  setOpen(false)
                }}
                className={cn(
                  'grid grid-cols-7 rounded-md transition-colors',
                  disabled ? 'cursor-not-allowed' : 'cursor-pointer',
                  !disabled && isSelectedRow && 'bg-primary/15',
                  !disabled && !isSelectedRow && hoveredRow === rowIdx && 'bg-muted'
                )}
              >
                {week.map((d, i) => (
                  <span
                    key={i}
                    className={cn(
                      'py-1 text-center text-xs',
                      disabled ? 'text-neutral-400' : 'text-neutral-800',
                      isSelectedRow && !disabled && 'font-semibold text-primary'
                    )}
                  >
                    {d.getDate()}
                  </span>
                ))}
              </div>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
