'use client'
import { useState, type ReactNode } from 'react'
import { Button } from './button'
import { Popover, PopoverContent, PopoverTrigger } from './popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from './command'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface DropdownOption {
  value: string
  label: string
  disabled?: boolean
  /** Optional leading color swatch (hex/CSS color), e.g. for topic color-coding */
  leadingDot?: string
}

export interface DropdownGroup {
  label: string
  options: DropdownOption[]
}

interface DropdownProps {
  value: string | undefined
  onChange: (value: string) => void
  /** Flat option list. Mutually exclusive with `groups`. */
  options?: DropdownOption[]
  /** Grouped option list (optgroup equivalent). Mutually exclusive with `options`. */
  groups?: DropdownGroup[]
  placeholder?: string
  /** Shows a search input in the popover. Default off — opt in for long option lists. */
  searchable?: boolean
  searchPlaceholder?: string
  size?: 'sm' | 'md'
  className?: string
  disabled?: boolean
  /** Leading icon rendered in the trigger, before the selected label. */
  icon?: ReactNode
  triggerId?: string
  'aria-label'?: string
}

export function Dropdown({
  value,
  onChange,
  options,
  groups,
  placeholder,
  searchable = false,
  searchPlaceholder,
  size = 'md',
  className,
  disabled,
  icon,
  triggerId,
  ...aria
}: DropdownProps) {
  const [open, setOpen] = useState(false)
  const flatAll = groups ? groups.flatMap(g => g.options) : (options ?? [])
  const selected = flatAll.find(o => o.value === value)

  function renderItem(o: DropdownOption) {
    return (
      <CommandItem
        key={o.value}
        value={o.label}
        disabled={o.disabled}
        onSelect={() => {
          if (o.disabled) return
          onChange(o.value)
          setOpen(false)
        }}
        className="justify-between gap-2 text-xs"
      >
        <span className="flex items-center gap-2 truncate">
          {o.leadingDot && (
            <span
              className="inline-block h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: o.leadingDot }}
            />
          )}
          <span className="truncate">{o.label}</span>
        </span>
        {value === o.value && <Check className="h-3.5 w-3.5 shrink-0" />}
      </CommandItem>
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={triggerId}
          type="button"
          variant="outline"
          size={size === 'sm' ? 'sm' : 'default'}
          disabled={disabled}
          className={cn(
            'justify-between font-normal gap-1.5',
            size === 'sm' && 'h-8 text-xs px-2.5',
            className,
          )}
          {...aria}
        >
          <span className="flex items-center gap-1.5 truncate">
            {icon}
            {selected?.leadingDot && (
              <span
                className="inline-block h-2 w-2 rounded-full shrink-0"
                style={{ backgroundColor: selected.leadingDot }}
              />
            )}
            <span className={cn('truncate', !selected && 'text-muted-foreground')}>
              {selected ? selected.label : (placeholder ?? 'Select…')}
            </span>
          </span>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1" align="start">
        <Command>
          {searchable && <CommandInput placeholder={searchPlaceholder ?? 'Search…'} className="h-8 text-xs" />}
          <CommandList className="max-h-64">
            <CommandEmpty>No results.</CommandEmpty>
            {groups
              ? groups.map(g => (
                  <CommandGroup key={g.label} heading={g.label}>
                    {g.options.map(renderItem)}
                  </CommandGroup>
                ))
              : (options ?? []).map(renderItem)}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
