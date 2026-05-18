'use client'
import { useEffect, useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown } from 'lucide-react'

type DateMode = 'any' | 'after' | 'before' | 'range'

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
    from: string
    to: string
  }
}

export function DateFilter({
  label, after, before, onAfterChange, onBeforeChange, labels,
}: DateFilterProps) {
  const [mode, setMode] = useState<DateMode>('any')

  useEffect(() => {
    if (after && before) setMode('range')
    else if (after) setMode('after')
    else if (before) setMode('before')
    else setMode('any')
  }, [after, before])

  function handleModeChange(m: DateMode) {
    setMode(m)
    if (m === 'any') { onAfterChange(''); onBeforeChange('') }
    if (m === 'after') onBeforeChange('')
    if (m === 'before') onAfterChange('')
  }

  const hasDate = !!(after || before)

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {hasDate && <Badge variant="secondary" className="h-4 px-1 text-[10px]">1</Badge>}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-60 p-3 space-y-3" align="start">
        <div className="flex gap-1">
          {(['any', 'after', 'before', 'range'] as DateMode[]).map(m => (
            <button
              key={m}
              onClick={() => handleModeChange(m)}
              className={`flex-1 text-[10px] px-1 py-1 rounded border transition-colors ${
                mode === m
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:border-foreground'
              }`}
            >
              {labels[m]}
            </button>
          ))}
        </div>
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
