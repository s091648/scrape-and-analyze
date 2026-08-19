'use client'
import { useEffect, useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SlidersHorizontal, X, Heart } from 'lucide-react'
import { MultiSelectPopover } from '@/components/common/multi-select-popover'
import { DateFilter } from '@/components/common/date-filter'
import { fetchArticleFilterOriginalSources } from '@/lib/api/articles'
import { fetchTagGroups, type TagGroupOut } from '@/lib/api/tags'
import { fetchSourceCategories, type SourceEntry } from '@/lib/api/source-categories'
import { useI18n, useTopic } from '@/lib/providers'
import { useSession } from 'next-auth/react'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { GroupedTagSelect } from './grouped-tag-select'

// Long enough that rapid successive edits (ticking through several checkboxes, or typing/picking
// both ends of a date range) collapse into a single applied change and a single fetch, short
// enough that it still reads as "instant" once the user pauses — same idea as SearchBar's
// autocomplete debounce, just tuned looser since this drives a real list refetch, not a
// suggestions lookup.
const FILTER_APPLY_DEBOUNCE_MS = 500

interface FilterBarProps {
  aggregators: string[]
  originalSources: string[]
  tags: string[]
  tagGroups: string[]
  publishedAfter: string
  publishedBefore: string
  scrapedAfter: string
  scrapedBefore: string
  activeFilterCount: number
  favoritesOnly?: boolean
  onFavoritesToggle?: (v: boolean) => void
  onApply: (updates: {
    aggregator?: string[]
    original_source?: string[]
    tag?: string[]
    tag_group?: string[]
    published_after?: string
    published_before?: string
    scraped_after?: string
    scraped_before?: string
  }) => void
  /** Rendered at the right edge of the top row — e.g. <SortSelect /> — kept as a sibling component since sorting and filtering are independent concerns. */
  children?: ReactNode
}

export function FilterBar({
  aggregators: activeAggregators,
  originalSources: activeOriginalSources,
  tags: activeTags, tagGroups: activeTagGroups,
  publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
  activeFilterCount,
  favoritesOnly = false, onFavoritesToggle, onApply,
  children,
}: FilterBarProps) {
  const { t, locale } = useI18n()
  const { selectedTopicId } = useTopic()
  const { status } = useSession()
  const isAuthenticated = status === 'authenticated'
  const [open, setOpen] = useState(false)
  const [aggregatorOptions, setAggregatorOptions] = useState<SourceEntry[]>([])
  const [originalSourceOptions, setOriginalSourceOptions] = useState<string[]>([])
  const [tagGroupOptions, setTagGroupOptions] = useState<TagGroupOut[]>([])

  const [draftAggregators, setDraftAggregators] = useState(activeAggregators)
  const [draftOriginalSources, setDraftOriginalSources] = useState(activeOriginalSources)
  const [draftTags, setDraftTags] = useState(activeTags)
  const [draftTagGroups, setDraftTagGroups] = useState(activeTagGroups)
  const [draftPubAfter, setDraftPubAfter] = useState(publishedAfter)
  const [draftPubBefore, setDraftPubBefore] = useState(publishedBefore)
  const [draftScrapedAfter, setDraftScrapedAfter] = useState(scrapedAfter)
  const [draftScrapedBefore, setDraftScrapedBefore] = useState(scrapedBefore)

  useEffect(() => {
    void Promise.allSettled([
      fetchSourceCategories().then(cats => setAggregatorOptions(cats.aggregator ?? [])),
      fetchArticleFilterOriginalSources(selectedTopicId ?? undefined, locale).then(data => setOriginalSourceOptions(Array.isArray(data) ? data : [])),
      fetchTagGroups(selectedTopicId ?? undefined).then(setTagGroupOptions),
    ])
  }, [locale, selectedTopicId])

  useEffect(() => {
    setDraftAggregators(activeAggregators)
    setDraftOriginalSources(activeOriginalSources)
    setDraftTags(activeTags)
    setDraftTagGroups(activeTagGroups)
    setDraftPubAfter(publishedAfter)
    setDraftPubBefore(publishedBefore)
    setDraftScrapedAfter(scrapedAfter)
    setDraftScrapedBefore(scrapedBefore)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(activeAggregators), JSON.stringify(activeOriginalSources), JSON.stringify(activeTags), JSON.stringify(activeTagGroups), publishedAfter, publishedBefore, scrapedAfter, scrapedBefore])

  // Auto-applies on every draft change, debounced — so toggling several checkboxes in a row, or
  // filling in both ends of a date range, collapses into one `onApply` call instead of one per
  // click/keystroke, while still feeling instant (no separate "Apply" button to press). Comparing
  // against the *active* (already-applied) snapshot — not just "did draft change" — is what makes
  // this safe to leave unconditional: after onApply fires, the props-sync effect above resets
  // draft to match, so the debounced value settles back to equal the active snapshot and this
  // effect's next run is a no-op instead of re-applying the same filters forever.
  const draftFiltersKey = JSON.stringify({
    aggregator: draftAggregators, original_source: draftOriginalSources,
    tag: draftTags, tag_group: draftTagGroups,
    published_after: draftPubAfter, published_before: draftPubBefore,
    scraped_after: draftScrapedAfter, scraped_before: draftScrapedBefore,
  })
  const debouncedDraftFiltersKey = useDebouncedValue(draftFiltersKey, FILTER_APPLY_DEBOUNCE_MS)

  useEffect(() => {
    const activeFiltersKey = JSON.stringify({
      aggregator: activeAggregators, original_source: activeOriginalSources,
      tag: activeTags, tag_group: activeTagGroups,
      published_after: publishedAfter, published_before: publishedBefore,
      scraped_after: scrapedAfter, scraped_before: scrapedBefore,
    })
    if (debouncedDraftFiltersKey === activeFiltersKey) return
    onApply(JSON.parse(debouncedDraftFiltersKey))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedDraftFiltersKey])

  function handleClear() {
    setDraftAggregators([]); setDraftOriginalSources([]); setDraftTags([]); setDraftTagGroups([])
    setDraftPubAfter(''); setDraftPubBefore('')
    setDraftScrapedAfter(''); setDraftScrapedBefore('')
    // Bypasses the debounce above — clearing is an explicit, immediate action.
    onApply({ aggregator: [], original_source: [], tag: [], tag_group: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '' })
    setOpen(false)
  }

  const dateLabels = {
    any: t('filterBar.any'),
    after: t('filterBar.after'),
    before: t('filterBar.before'),
    range: t('filterBar.range'),
    recent: t('filterBar.recent'),
    from: t('filterBar.from'),
    to: t('filterBar.to'),
    days: t('filterBar.days'),
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs cursor-pointer"
          onClick={() => setOpen(o => !o)}
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          {t('filterBar.filters')}
          {activeFilterCount > 0 && (
            <Badge variant="secondary" className="h-4 px-1 text-[10px]">{activeFilterCount}</Badge>
          )}
        </Button>
        {children && <div className="ml-auto">{children}</div>}
      </div>

      {open && (
        <div className="flex flex-wrap items-start gap-2 p-3 rounded-xl border border-border bg-muted/30">
          {isAuthenticated && (
            <Button
              variant={favoritesOnly ? 'default' : 'outline'}
              size="sm"
              className="h-8 gap-1.5 text-xs cursor-pointer"
              onClick={() => onFavoritesToggle?.(!favoritesOnly)}
            >
              <Heart className={`h-3.5 w-3.5 ${favoritesOnly ? 'fill-current' : ''}`} />
              {t('filterBar.favoritesOnly')}
            </Button>
          )}
          <MultiSelectPopover
            label={t('filterBar.aggregator')}
            options={aggregatorOptions}
            selected={draftAggregators}
            onChange={setDraftAggregators}
            searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.aggregator').toLowerCase()}…`}
          />
          <MultiSelectPopover
            label={t('filterBar.source')}
            options={originalSourceOptions}
            selected={draftOriginalSources}
            onChange={setDraftOriginalSources}
            searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.source').toLowerCase()}…`}
          />
          <GroupedTagSelect
            label={t('filterBar.tag')}
            groups={tagGroupOptions}
            selectedTags={draftTags}
            selectedGroups={draftTagGroups}
            onTagsChange={setDraftTags}
            onGroupsChange={setDraftTagGroups}
            searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.tag').toLowerCase()}…`}
            emptyText={t('filterBar.noTagsFound')}
          />
          <DateFilter
            label={t('filterBar.published')}
            after={draftPubAfter}
            before={draftPubBefore}
            onAfterChange={setDraftPubAfter}
            onBeforeChange={setDraftPubBefore}
            labels={dateLabels}
          />
          <DateFilter
            label={t('filterBar.scraped')}
            after={draftScrapedAfter}
            before={draftScrapedBefore}
            onAfterChange={setDraftScrapedAfter}
            onBeforeChange={setDraftScrapedBefore}
            labels={dateLabels}
          />
          {activeFilterCount > 0 && (
            <div className="flex gap-2 ml-auto">
              <Button variant="ghost" size="sm" className="h-8 text-xs gap-1 cursor-pointer" onClick={handleClear}>
                <X className="h-3 w-3" /> {t('filterBar.clear')}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
