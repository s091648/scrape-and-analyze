'use client'
import useSWR from 'swr'
import { fetchTagGroups, fetchPendingSuggestions, type TagGroupOut, type SuggestionOut } from '@/lib/api/tags'

export interface TagGroupsFeedResult {
  groups: TagGroupOut[]
  suggestions: SuggestionOut[]
}

interface UseTagGroupsFeedArgs {
  enabled: boolean
  topicId?: string
  includeSimilarity: boolean
  isAdmin: boolean
  token?: string
  /** SSR-seeded groups for the current topic — see tags-page-content.tsx's fingerprint gating
   * for when this is (and stops being) passed. Suggestions have no SSR counterpart (admin-only,
   * fetched client-side even on the SSR-seeded first render — matches pre-SWR behavior). */
  fallbackData?: TagGroupsFeedResult
}

/** Read-only cache/revalidation layer for the tags page's list — deliberately does NOT try to
 * mirror every optimistic drag/merge/move edit back into this cache (see tags-page-content.tsx's
 * own comment on why: those edits live in local `groups`/`suggestions` state, same as before this
 * hook existed). What this buys: switching topics away and back, or revisiting /tags in a new
 * tab, reuses this cache and revalidates instead of always re-fetching from scratch — and skips
 * the redundant client-side duplicate of the SSR fetch app/tags/page.tsx just did
 * (`revalidateOnMount: false` while `fallbackData` is present). */
export function useTagGroupsFeed({
  enabled, topicId, includeSimilarity, isAdmin, token, fallbackData,
}: UseTagGroupsFeedArgs) {
  const key = enabled
    ? (['tag-groups-feed', topicId ?? null, includeSimilarity, isAdmin, token ?? null] as const)
    : null

  const { data, isLoading } = useSWR<TagGroupsFeedResult>(
    key,
    () => Promise.all([
      fetchTagGroups(topicId, includeSimilarity),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ]).then(([groups, suggestions]) => ({ groups, suggestions })),
    { fallbackData, revalidateOnMount: fallbackData ? false : undefined },
  )

  return { data, isLoading }
}
