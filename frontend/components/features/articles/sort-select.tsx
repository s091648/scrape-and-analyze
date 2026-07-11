'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandItem, CommandList } from '@/components/ui/command'
import { ArrowUpDown, ArrowUp, ArrowDown, Check, ChevronDown } from 'lucide-react'
import { useI18n } from '@/lib/providers'

const SORT_OPTIONS = [
  { value: 'scraped_at', labelKey: 'filterBar.sortScrapedAt' },
  { value: 'published_at', labelKey: 'filterBar.sortPublishedAt' },
  { value: 'citation_count', labelKey: 'filterBar.sortCitationCount' },
  { value: 'view_count', labelKey: 'filterBar.sortViewCount' },
  { value: 'source', labelKey: 'filterBar.sortSource' },
  { value: 'title', labelKey: 'filterBar.sortTitle' },
] as const

interface SortSelectProps {
  sort: string
  order: string
  onSortChange: (sort: string) => void
  onOrderChange: (order: string) => void
}

export function SortSelect({ sort, order, onSortChange, onOrderChange }: SortSelectProps) {
  const { t } = useI18n()
  const [sortOpen, setSortOpen] = useState(false)
  const selectedSortOption = SORT_OPTIONS.find(o => o.value === sort) ?? SORT_OPTIONS[0]
  const isDescending = order !== 'asc'

  return (
    <div className="flex items-center gap-1">
      <Popover open={sortOpen} onOpenChange={setSortOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1.5 text-xs cursor-pointer"
            title={t('filterBar.sortTooltip')}
            aria-label={`${t('filterBar.sortBy')}: ${t(selectedSortOption.labelKey)}`}
          >
            <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">{t('filterBar.sortBy')}:</span>
            {t(selectedSortOption.labelKey)}
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-44 p-1" align="end">
          <Command>
            <CommandList>
              {SORT_OPTIONS.map(o => (
                <CommandItem
                  key={o.value}
                  value={o.value}
                  onSelect={() => {
                    onSortChange(o.value)
                    setSortOpen(false)
                  }}
                  className="justify-between gap-2 text-xs"
                >
                  {t(o.labelKey)}
                  {sort === o.value && <Check className="h-3.5 w-3.5" />}
                </CommandItem>
              ))}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      <Button
        variant="outline"
        size="sm"
        className="h-8 w-8 p-0 cursor-pointer"
        onClick={() => onOrderChange(isDescending ? 'asc' : 'desc')}
        title={isDescending ? t('filterBar.sortDescending') : t('filterBar.sortAscending')}
        aria-label={isDescending ? t('filterBar.sortDescending') : t('filterBar.sortAscending')}
      >
        {isDescending ? <ArrowDown className="h-3.5 w-3.5" /> : <ArrowUp className="h-3.5 w-3.5" />}
      </Button>
    </div>
  )
}
