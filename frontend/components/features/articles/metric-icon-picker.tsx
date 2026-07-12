'use client'
import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { DEFAULT_METRIC_ICON, METRIC_ICON_NAMES, METRIC_ICONS } from './metric-icons'

interface MetricIconPickerProps {
  value: string | null | undefined
  onChange: (name: string) => void
  /** icon_name -> label of the OTHER metric definition currently using it */
  disabledIcons: Map<string, string>
  ariaLabel: string
}

export function MetricIconPicker({ value, onChange, disabledIcons, ariaLabel }: MetricIconPickerProps) {
  const [open, setOpen] = useState(false)
  const TriggerIcon = (value && METRIC_ICONS[value]) || DEFAULT_METRIC_ICON

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          className="rounded p-1 -m-1 cursor-pointer text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <TriggerIcon className="h-4 w-4 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-2" align="start">
        <TooltipProvider>
          <div className="grid grid-cols-5 gap-1">
            {METRIC_ICON_NAMES.map(name => {
              const IconCmp = METRIC_ICONS[name]
              const isSelected = name === value
              const usedByLabel = disabledIcons.get(name)
              const isDisabled = !!usedByLabel && !isSelected

              const button = (
                <button
                  key={name}
                  type="button"
                  aria-label={name}
                  aria-disabled={isDisabled}
                  onClick={() => {
                    if (isDisabled) return
                    onChange(name)
                    setOpen(false)
                  }}
                  className={cn(
                    'flex h-9 w-9 items-center justify-center rounded-md border transition-colors',
                    isDisabled
                      ? 'opacity-30 cursor-not-allowed border-transparent'
                      : 'cursor-pointer border-transparent hover:bg-muted hover:border-border',
                    isSelected && 'ring-2 ring-primary border-primary bg-primary/10',
                  )}
                >
                  <IconCmp className="h-4 w-4" />
                </button>
              )

              if (!usedByLabel) return button

              return (
                <Tooltip key={name}>
                  <TooltipTrigger asChild>{button}</TooltipTrigger>
                  <TooltipContent>{usedByLabel}</TooltipContent>
                </Tooltip>
              )
            })}
          </div>
        </TooltipProvider>
      </PopoverContent>
    </Popover>
  )
}
