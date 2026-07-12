'use client'
import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown } from 'lucide-react'

type DateMode = 'any' | 'after' | 'before' | 'range' | 'recent'

interface DateFilterProps {
  label: string
  after: string
  before: string
  onAfterChange: (v: string) => void
  onBeforeChange: (v: string) => void
  labels: {
    any: string
    after: string
    before: string
    range: string
    recent: string
    from: string
    to: string
    days: string
  }
}

function toDateString(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function recentAfterDate(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return toDateString(d)
}

export function DateFilter({
  label, after, before, onAfterChange, onBeforeChange, labels,
}: DateFilterProps) {
  // Derive initial mode from props once at mount. Mode is then driven purely
  // by user clicks — no useEffect re-derivation, which caused the bug where
  // clicking "Before" (which clears `after`) would make both empty and reset to 'any'.
  const [mode, setMode] = useState<DateMode>(() => {
    if (after && before) return 'range'
    if (after && !before) return 'after'
    if (!after && before) return 'before'
    return 'any'
  })
  const [recentDays, setRecentDays] = useState(30)

  function handleModeChange(m: DateMode) {
    setMode(m)
    if (m === 'any') { onAfterChange(''); onBeforeChange('') }
    if (m === 'after') onBeforeChange('')
    if (m === 'before') onAfterChange('')
    if (m === 'recent') {
      onAfterChange(recentAfterDate(recentDays))
      onBeforeChange('')
    }
  }

  function handleRecentDaysChange(days: number) {
    const clamped = Math.min(180, Math.max(1, days))
    setRecentDays(clamped)
    onAfterChange(recentAfterDate(clamped))
    onBeforeChange('')
  }

  const hasDate = !!(after || before)
  const modes: DateMode[] = ['any', 'after', 'before', 'range', 'recent']

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {hasDate && <Badge variant="secondary" className="h-4 px-1 text-[10px]">1</Badge>}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-3 space-y-3" align="start">
        <div className="flex gap-1">
          {modes.map(m => (
            <button
              key={m}
              onClick={() => handleModeChange(m)}
              className={`flex-1 text-[10px] px-1 py-1 rounded border transition-colors cursor-pointer ${
                mode === m
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:border-foreground'
              }`}
            >
              {labels[m]}
            </button>
          ))}
        </div>
        {mode === 'recent' && (
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={180}
              value={recentDays}
              onChange={e => handleRecentDaysChange(Number(e.target.value))}
              className="w-16 text-xs border border-border rounded px-2 py-1 bg-background"
            />
            <span className="text-xs text-muted-foreground">{labels.days}</span>
          </div>
        )}
        {(mode === 'after' || mode === 'range') && (
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">{labels.from}</label>
            <input
              type="date"
              value={after}
              onChange={e => onAfterChange(e.target.value)}
              className="w-full text-xs border border-border rounded px-2 py-1 bg-background"
            />
          </div>
        )}
        {(mode === 'before' || mode === 'range') && (
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">{labels.to}</label>
            <input
              type="date"
              value={before}
              onChange={e => onBeforeChange(e.target.value)}
              className="w-full text-xs border border-border rounded px-2 py-1 bg-background"
            />
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
