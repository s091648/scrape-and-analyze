'use client'

import { useState, useEffect } from 'react'
import { Command, CommandInput } from '@/components/ui/command'
import { useI18n } from '@/lib/providers'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { fetchAutocompleteSuggestions, type AutocompleteSuggestion } from '@/lib/api/search'
import { AutocompleteDropdown } from './autocomplete-dropdown'

const MAX_AUTOCOMPLETE_QUERY_LEN = 8 // must match backend's SEARCH_AUTOCOMPLETE_MAX_QUERY_LEN
const AUTOCOMPLETE_DEBOUNCE_MS = 300

interface SearchBarProps {
  /** Current applied search query (from the URL `q` param) — kept in sync so browser
   * back/forward and external navigation reflect in the input too. */
  value: string
  onSubmit: (query: string) => void
  onClear: () => void
  topicId?: string
  locale?: string
  token?: string
}

export function SearchBar({ value, onSubmit, onClear, topicId, locale, token }: SearchBarProps) {
  const { t } = useI18n()
  const [draft, setDraft] = useState(value)
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([])

  // Keep the input in sync when `value` changes externally (e.g. browser back/forward,
  // or the search being cleared elsewhere) without clobbering in-progress typing on
  // every keystroke (this effect only fires when the *external* value changes).
  useEffect(() => {
    setDraft(value)
  }, [value])

  // FR-005: throttles how often autocomplete actually fires while typing — the effect
  // below re-runs only once `draft` has stopped changing for AUTOCOMPLETE_DEBOUNCE_MS,
  // not on every keystroke.
  const debouncedDraft = useDebouncedValue(draft, AUTOCOMPLETE_DEBOUNCE_MS)

  // FR-004/FR-006: fetch suggestions once typing settles. AbortController discards a
  // superseded in-flight lookup's response — the same pattern used for search itself
  // (articles-page-content.tsx) — so a slow earlier request's result can never overwrite
  // a faster later one (e.g. a rapid type-then-delete past a debounce boundary). Skips
  // the request entirely past the backend's suffix-prefix cap (contracts/search-api.md's
  // frontend-guard note) — the backend would truncate+filter to the same effect anyway,
  // so this just saves the round trip.
  useEffect(() => {
    const trimmed = debouncedDraft.trim()
    if (!trimmed || trimmed.length > MAX_AUTOCOMPLETE_QUERY_LEN) {
      setSuggestions([])
      return
    }
    const controller = new AbortController()
    fetchAutocompleteSuggestions(trimmed, topicId, locale, token, controller.signal)
      .then(data => setSuggestions(data.suggestions))
      .catch(err => { if ((err as Error)?.name !== 'AbortError') throw err })
    return () => controller.abort()
  }, [debouncedDraft, topicId, locale, token])

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== 'Enter') return
    const trimmed = draft.trim()
    if (trimmed) applySearch(trimmed)
    else onClear()
  }

  function handleChange(next: string) {
    setDraft(next)
    if (next.trim() === '' && value !== '') onClear()
  }

  function applySearch(term: string) {
    onSubmit(term)
    setSuggestions([]) // closes the dropdown (Acceptance Scenario 2)
  }

  return (
    <Command shouldFilter={false} className="rounded-md border border-border">
      <CommandInput
        value={draft}
        onValueChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={t('search.placeholder')}
        aria-label={t('search.placeholder')}
      />
      {draft.trim() && suggestions.length > 0 && (
        <AutocompleteDropdown suggestions={suggestions} onSelect={applySearch} query={debouncedDraft.trim()} />
      )}
    </Command>
  )
}
