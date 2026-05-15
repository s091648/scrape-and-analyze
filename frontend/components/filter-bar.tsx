'use client'
import { useEffect, useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Command, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SlidersHorizontal, ChevronDown, X } from 'lucide-react'
import { apiFetch } from '@/lib/api-fetch'
import { useI18n } from '@/i18n'

type DateMode = 'any' | 'after' | 'before' | 'range'

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

function MultiSelectPopover({
  label, options, selected, onChange,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (val: string[]) => void
}) {
  const { t } = useI18n()
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
          <CommandInput placeholder={`${t('filterBar.search')} ${label.toLowerCase()}…`} className="h-8 text-xs" />
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

function DateFilter({
  label, after, before, onAfterChange, onBeforeChange,
}: {
  label: string
  after: string
  before: string
  onAfterChange: (v: string) => void
  onBeforeChange: (v: string) => void
}) {
  const { t } = useI18n()
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

  const modeLabels: Record<DateMode, string> = {
    any: t('filterBar.any'),
    after: t('filterBar.after'),
    before: t('filterBar.before'),
    range: t('filterBar.range'),
  }

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
              {modeLabels[m]}
            </button>
          ))}
        </div>
        {(mode === 'after' || mode === 'range') && (
          <div>
            <label className="text-[10px] text-muted-foreground block mb-1">{t('filterBar.from')}</label>
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
            <label className="text-[10px] text-muted-foreground block mb-1">{t('filterBar.to')}</label>
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

export function FilterBar({
  sources: activeSources, tags: activeTags,
  publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
  activeFilterCount, onApply,
}: FilterBarProps) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [sourceOptions, setSourceOptions] = useState<string[]>([])
  const [tagOptions, setTagOptions] = useState<string[]>([])

  const [draftSources, setDraftSources] = useState(activeSources)
  const [draftTags, setDraftTags] = useState(activeTags)
  const [draftPubAfter, setDraftPubAfter] = useState(publishedAfter)
  const [draftPubBefore, setDraftPubBefore] = useState(publishedBefore)
  const [draftScrapedAfter, setDraftScrapedAfter] = useState(scrapedAfter)
  const [draftScrapedBefore, setDraftScrapedBefore] = useState(scrapedBefore)

  useEffect(() => {
    apiFetch('/articles/filters/sources').then(r => r.json()).then(setSourceOptions)
    apiFetch('/articles/filters/tags').then(r => r.json()).then(setTagOptions)
  }, [])

  // Sync draft when URL changes (back/forward navigation)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setDraftSources(activeSources)
    setDraftTags(activeTags)
    setDraftPubAfter(publishedAfter)
    setDraftPubBefore(publishedBefore)
    setDraftScrapedAfter(scrapedAfter)
    setDraftScrapedBefore(scrapedBefore)
  }, [JSON.stringify(activeSources), JSON.stringify(activeTags), publishedAfter, publishedBefore, scrapedAfter, scrapedBefore]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleApply() {
    onApply({
      source: draftSources,
      tag: draftTags,
      published_after: draftPubAfter,
      published_before: draftPubBefore,
      scraped_after: draftScrapedAfter,
      scraped_before: draftScrapedBefore,
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
          />
          <MultiSelectPopover
            label={t('filterBar.tag')}
            options={tagOptions}
            selected={draftTags}
            onChange={setDraftTags}
          />
          <DateFilter
            label={t('filterBar.published')}
            after={draftPubAfter}
            before={draftPubBefore}
            onAfterChange={setDraftPubAfter}
            onBeforeChange={setDraftPubBefore}
          />
          <DateFilter
            label={t('filterBar.scraped')}
            after={draftScrapedAfter}
            before={draftScrapedBefore}
            onAfterChange={setDraftScrapedAfter}
            onBeforeChange={setDraftScrapedBefore}
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
