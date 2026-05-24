'use client'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SlidersHorizontal, X } from 'lucide-react'
import { MultiSelectPopover } from '@/components/common/multi-select-popover'
import { DateFilter } from '@/components/common/date-filter'
import { fetchArticleFilterSources } from '@/lib/api/articles'
import { fetchTagGroups, type TagGroupOut } from '@/lib/api/tags'
import { useI18n, useTopic } from '@/lib/providers'
import { GroupedTagSelect } from './grouped-tag-select'

interface FilterBarProps {
  sources: string[]
  tags: string[]
  publishedAfter: string
  publishedBefore: string
  scrapedAfter: string
  scrapedBefore: string
  activeFilterCount: number
  onApply: (updates: {
    source?: string[]
    tag?: string[]
    published_after?: string
    published_before?: string
    scraped_after?: string
    scraped_before?: string
  }) => void
}

export function FilterBar({
  sources: activeSources, tags: activeTags,
  publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
  activeFilterCount, onApply,
}: FilterBarProps) {
  const { t, locale } = useI18n()
  const { selectedTopicId } = useTopic()
  const [open, setOpen] = useState(false)
  const [sourceOptions, setSourceOptions] = useState<string[]>([])
  const [tagGroups, setTagGroups] = useState<TagGroupOut[]>([])

  const [draftSources, setDraftSources] = useState(activeSources)
  const [draftTags, setDraftTags] = useState(activeTags)
  const [draftPubAfter, setDraftPubAfter] = useState(publishedAfter)
  const [draftPubBefore, setDraftPubBefore] = useState(publishedBefore)
  const [draftScrapedAfter, setDraftScrapedAfter] = useState(scrapedAfter)
  const [draftScrapedBefore, setDraftScrapedBefore] = useState(scrapedBefore)

  useEffect(() => {
    fetchArticleFilterSources(locale).then(setSourceOptions)
    fetchTagGroups(selectedTopicId ?? undefined).then(setTagGroups)
  }, [locale, selectedTopicId])

  useEffect(() => {
    setDraftSources(activeSources)
    setDraftTags(activeTags)
    setDraftPubAfter(publishedAfter)
    setDraftPubBefore(publishedBefore)
    setDraftScrapedAfter(scrapedAfter)
    setDraftScrapedBefore(scrapedBefore)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(activeSources), JSON.stringify(activeTags), publishedAfter, publishedBefore, scrapedAfter, scrapedBefore])

  function handleApply() {
    onApply({
      source: draftSources, tag: draftTags,
      published_after: draftPubAfter, published_before: draftPubBefore,
      scraped_after: draftScrapedAfter, scraped_before: draftScrapedBefore,
    })
    setOpen(false)
  }

  function handleClear() {
    setDraftSources([]); setDraftTags([])
    setDraftPubAfter(''); setDraftPubBefore('')
    setDraftScrapedAfter(''); setDraftScrapedBefore('')
    onApply({ source: [], tag: [], published_after: '', published_before: '', scraped_after: '', scraped_before: '' })
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
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={() => setOpen(o => !o)}
      >
        <SlidersHorizontal className="h-3.5 w-3.5" />
        {t('filterBar.filters')}
        {activeFilterCount > 0 && (
          <Badge variant="secondary" className="h-4 px-1 text-[10px]">{activeFilterCount}</Badge>
        )}
      </Button>

      {open && (
        <div className="flex flex-wrap items-start gap-2 p-3 rounded-xl border border-border bg-muted/30">
          <MultiSelectPopover
            label={t('filterBar.source')}
            options={sourceOptions}
            selected={draftSources}
            onChange={setDraftSources}
            searchPlaceholder={`${t('filterBar.search')} ${t('filterBar.source').toLowerCase()}…`}
          />
          <GroupedTagSelect
            label={t('filterBar.tag')}
            groups={tagGroups}
            selected={draftTags}
            onChange={setDraftTags}
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
          <div className="flex gap-2 ml-auto">
            {activeFilterCount > 0 && (
              <Button variant="ghost" size="sm" className="h-8 text-xs gap-1" onClick={handleClear}>
                <X className="h-3 w-3" /> {t('filterBar.clear')}
              </Button>
            )}
            <Button size="sm" className="h-8 text-xs" onClick={handleApply}>{t('filterBar.apply')}</Button>
          </div>
        </div>
      )}
    </div>
  )
}
