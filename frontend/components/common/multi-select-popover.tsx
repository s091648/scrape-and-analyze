'use client'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown } from 'lucide-react'

interface MultiSelectPopoverProps {
  label: string
  options: string[]
  selected: string[]
  onChange: (val: string[]) => void
  searchPlaceholder?: string
}

export function MultiSelectPopover({
  label, options, selected, onChange, searchPlaceholder,
}: MultiSelectPopoverProps) {
  function toggle(v: string) {
    onChange(selected.includes(v) ? selected.filter(s => s !== v) : [...selected, v])
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {selected.length > 0 && (
            <Badge variant="secondary" className="h-4 px-1 text-[10px]">{selected.length}</Badge>
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
            {options.map(opt => (
              <CommandItem key={opt} value={opt} onSelect={() => toggle(opt)} className="gap-2 text-xs">
                <Checkbox checked={selected.includes(opt)} className="h-3.5 w-3.5" />
                {opt}
              </CommandItem>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
