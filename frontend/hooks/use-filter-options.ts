'use client'
import useSWR from 'swr'
import { fetchArticleFilterOriginalSources } from '@/lib/api/articles'
import { fetchTagGroups, type TagGroupOut } from '@/lib/api/tags'
import { fetchSourceCategories, type SourceEntry } from '@/lib/api/source-categories'

export interface FilterOptions {
  aggregatorOptions: SourceEntry[]
  originalSourceOptions: string[]
  tagGroupOptions: TagGroupOut[]
}

const EMPTY_OPTIONS: FilterOptions = { aggregatorOptions: [], originalSourceOptions: [], tagGroupOptions: [] }

/** Shared across every `FilterBar` instance — it's mounted separately on `/articles` and
 * `/graph`, each previously re-fetching all three option lists on its own mount. Keyed by
 * (topicId, locale) so switching between those two pages (or navigating away and back) with the
 * same topic selected reuses this cache instead of refetching from scratch. */
export function useFilterOptions(topicId?: string, locale?: string) {
  const { data, isLoading } = useSWR<FilterOptions>(
    ['filter-options', topicId ?? null, locale ?? 'en'],
    // Promise.allSettled (not .all) — matches the pre-SWR effect's Promise.allSettled fault
    // tolerance: one list failing to load shouldn't blank out the other two.
    async () => {
      const [categoriesResult, originalSourcesResult, tagGroupsResult] = await Promise.allSettled([
        fetchSourceCategories(),
        fetchArticleFilterOriginalSources(topicId, locale),
        fetchTagGroups(topicId),
      ])
      const originalSources = originalSourcesResult.status === 'fulfilled' ? originalSourcesResult.value : []
      return {
        aggregatorOptions: categoriesResult.status === 'fulfilled' ? (categoriesResult.value.aggregator ?? []) : [],
        originalSourceOptions: Array.isArray(originalSources) ? originalSources : [],
        tagGroupOptions: tagGroupsResult.status === 'fulfilled' ? tagGroupsResult.value : [],
      }
    },
  )
  return { ...(data ?? EMPTY_OPTIONS), isLoading }
}
