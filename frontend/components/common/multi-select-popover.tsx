'use client'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown } from 'lucide-react'

export interface SelectOption {
  value: string
  label: string
}

interface MultiSelectPopoverProps {
  label: string
  options: (string | SelectOption)[]
  selected: string[]
  onChange: (val: string[]) => void
  searchPlaceholder?: string
}

export function MultiSelectPopover({
  label, options, selected, onChange, searchPlaceholder,
}: MultiSelectPopoverProps) {
  const normalized = options.map(o => typeof o === 'string' ? { value: o, label: o } : o)

  function toggle(v: string) {
    onChange(selected.includes(v) ? selected.filter(s => s !== v) : [...selected, v])
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {selected.length > 0 && (
            <Badge variant="secondary" className="h-4 min-w-4 rounded-sm px-1 text-[10px] tabular-nums">
              {selected.length}
            </Badge>
          )}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-52 p-0" align="start">
        <Command>
          <CommandInput
            placeholder={searchPlaceholder ?? `Search ${label.toLowerCase()}…`}
            className="h-8 text-xs"
          />
          <CommandList className="max-h-52">
            {normalized.map(opt => (
              <CommandItem key={opt.value} value={opt.value} onSelect={() => toggle(opt.value)} className="gap-2 text-xs">
                <Checkbox checked={selected.includes(opt.value)} className="h-3.5 w-3.5" />
                {opt.label}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
