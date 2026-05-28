'use client'
import { useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { TagGroupOut } from '@/lib/api/tags'

interface GroupedTagSelectProps {
  label: string
  groups: TagGroupOut[]
  selectedTags: string[]
  selectedGroups: string[]
  onTagsChange: (val: string[]) => void
  onGroupsChange: (val: string[]) => void
  searchPlaceholder?: string
  emptyText?: string
}

function highlight(text: string, query: string) {
  if (!query) return <>{text}</>
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-yellow-100 dark:bg-yellow-900/40 rounded-sm px-0.5 not-italic">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}

export function GroupedTagSelect({
  label, groups, selectedTags, selectedGroups, onTagsChange, onGroupsChange,
  searchPlaceholder = 'Search tags…',
  emptyText = 'No tags found',
}: GroupedTagSelectProps) {
  const [search, setSearch] = useState('')
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())  // keyed by group name

  const q = search.toLowerCase()

  const visibleGroups = groups.map(g => ({
    ...g,
    matchedTags: search ? g.tags.filter(t => t.name.toLowerCase().includes(q)) : g.tags,
  })).filter(g => !search || g.display_name.toLowerCase().includes(q) || g.matchedTags.length > 0)

  function toggleGroup(g: TagGroupOut) {
    const isSelected = selectedGroups.includes(g.name)
    if (isSelected) {
      onGroupsChange(selectedGroups.filter(n => n !== g.name))
    } else {
      // selecting a group clears any individual tag selections for that group to avoid redundancy
      const groupTagNames = g.tags.map(t => t.name)
      onGroupsChange([...selectedGroups, g.name])
      onTagsChange(selectedTags.filter(t => !groupTagNames.includes(t)))
    }
  }

  function toggleTag(tag: { name: string }, group: TagGroupOut) {
    const isSelected = selectedTags.includes(tag.name)
    if (isSelected) {
      onTagsChange(selectedTags.filter(s => s !== tag.name))
    } else {
      // selecting an individual tag deselects its parent group
      onGroupsChange(selectedGroups.filter(n => n !== group.name))
      onTagsChange([...selectedTags, tag.name])
    }
  }

  function toggleExpand(name: string) {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const totalSelected = selectedGroups.length + selectedTags.length

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          {label}
          {totalSelected > 0 && (
            <Badge variant="secondary" className="h-4 px-1 text-[10px]">{totalSelected}</Badge>
          )}
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="start">
        <div className="px-3 py-2 border-b border-border">
          <input
            className="w-full text-xs bg-transparent outline-none placeholder:text-muted-foreground"
            placeholder={searchPlaceholder}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-72 overflow-y-auto py-1">
          {visibleGroups.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">{emptyText}</p>
          )}
          {visibleGroups.map(g => {
            const groupSelected = selectedGroups.includes(g.name)
            const someTagsSelected = g.tags.some(t => selectedTags.includes(t.name))
            const isExpanded = expandedGroups.has(g.name) || !!search

            return (
              <div key={g.id}>
                {/* Group row */}
                <div className="flex items-center gap-1.5 px-2 py-1.5 hover:bg-muted/50 cursor-pointer">
                  <Checkbox
                    checked={groupSelected ? true : someTagsSelected ? 'indeterminate' : false}
                    onCheckedChange={() => toggleGroup(g)}
                    className="h-3.5 w-3.5 shrink-0"
                  />
                  {g.color_hex && (
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: g.color_hex }} />
                  )}
                  <button
                    className="flex-1 text-xs font-medium text-left"
                    onClick={() => toggleGroup(g)}
                  >
                    {highlight(g.display_name, search)}
                  </button>
                  <button
                    className="text-muted-foreground hover:text-foreground shrink-0"
                    onClick={e => { e.stopPropagation(); toggleExpand(g.name) }}
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    {isExpanded
                      ? <ChevronDown className="h-3 w-3" />
                      : <ChevronRight className="h-3 w-3" />
                    }
                  </button>
                </div>

                {/* Tag rows */}
                {isExpanded && g.matchedTags.map(tag => (
                  <button
                    key={tag.id}
                    className="flex items-center gap-2 pl-7 pr-2 py-1 w-full hover:bg-muted/50 text-left"
                    onClick={() => toggleTag(tag, g)}
                  >
                    <Checkbox
                      checked={groupSelected || selectedTags.includes(tag.name)}
                      onCheckedChange={() => toggleTag(tag, g)}
                      className="h-3 w-3 shrink-0 pointer-events-none"
                    />
                    <span className="text-xs">{highlight(tag.name, search)}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
