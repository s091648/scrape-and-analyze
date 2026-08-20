'use client'

import { CommandList, CommandItem, CommandEmpty, CommandGroup } from '@/components/ui/command'
import { useI18n } from '@/lib/providers'
import { highlightMatch } from '@/lib/highlight-match'
import type { AutocompleteSuggestion } from '@/lib/api/search'

interface AutocompleteDropdownProps {
  suggestions: AutocompleteSuggestion[]
  onSelect: (term: string) => void
  /** Currently typed text — highlighted wherever it occurs within each suggestion
   * (not just at the start, matching the contains-anywhere index behind these
   * suggestions). */
  query: string
}

/** Renders inside the same <Command> root as SearchBar's <CommandInput> — cmdk's
 * keyboard navigation (arrow keys, Enter-to-select) requires CommandList/CommandItem to
 * share that context, so this is composed as a child of SearchBar, not a standalone
 * Command instance (FR-004/FR-007). */
export function AutocompleteDropdown({ suggestions, onSelect, query }: AutocompleteDropdownProps) {
  const { t } = useI18n()

  return (
    <CommandList>
      <CommandEmpty>{t('search.noSuggestions')}</CommandEmpty>
      <CommandGroup>
        {suggestions.map((s, i) => (
          <CommandItem
            key={s.term}
            value={s.term}
            onSelect={() => onSelect(s.term)}
            className={`py-2.5 justify-between rounded-none ${i < suggestions.length - 1 ? 'border-b border-border' : ''}`}
          >
            <span>{highlightMatch(s.term, query)}</span>
            <span className="text-xs text-muted-foreground">{s.occurrence_count}</span>
          </CommandItem>
        ))}
      </CommandGroup>
    </CommandList>
  )
}
