'use client'
import { createContext, useContext, useCallback, useState } from 'react'

export interface PinnedArticle {
  id: string
  title: string
  tags?: string[]
}

/** One weekly report's sparkles-pin batch — frontend-only, never persisted. `articles` is the full
 * candidate set (kept stable even as some get unchecked) so the edit checklist can re-offer them. */
export interface PinnedGroup {
  id: string
  dateLabel: string
  articles: PinnedArticle[]
}

interface PinnedArticleContextValue {
  pinnedArticles: PinnedArticle[]
  togglePinnedArticle: (article: PinnedArticle) => void
  removePinnedArticle: (id: string) => void
  clearPinnedArticles: () => void
  isPinned: (id: string) => boolean
  /** Adds every article not already pinned; leaves already-pinned ones as-is (no duplicates, no toggle-off). */
  pinArticles: (articles: PinnedArticle[]) => void
  /** True only when every given id is currently pinned. Empty input is vacuously false (nothing to pin). */
  areAllPinned: (ids: string[]) => boolean
  pinnedGroups: PinnedGroup[]
  /** Upserts the group by id and pins every one of its articles (additive, see pinArticles). */
  pinGroup: (group: PinnedGroup) => void
  /** Toggles one article's pinned state within a group. Once the group's included count reaches
   * zero, the group itself is removed (no orphaned zero-count pill). */
  toggleGroupArticle: (groupId: string, articleId: string) => void
  /** Unpins every article in the group and removes it. */
  removeGroup: (groupId: string) => void
}

/** Shared store logic behind both pin contexts below — kept as a single hook so the two contexts
 * (per-article chat vs. weekly-report chat, which must NOT share pinned state, see index.tsx) don't
 * duplicate this reducer twice. */
function usePinnedArticleStore(): PinnedArticleContextValue {
  const [pinnedArticles, setPinnedArticles] = useState<PinnedArticle[]>([])
  const [pinnedGroups, setPinnedGroups] = useState<PinnedGroup[]>([])

  const togglePinnedArticle = useCallback((article: PinnedArticle) => {
    setPinnedArticles(prev =>
      prev.some(a => a.id === article.id)
        ? prev.filter(a => a.id !== article.id)
        : [...prev, article]
    )
  }, [])

  const removePinnedArticle = useCallback((id: string) => {
    setPinnedArticles(prev => prev.filter(a => a.id !== id))
  }, [])

  const clearPinnedArticles = useCallback(() => setPinnedArticles([]), [])

  const isPinned = useCallback(
    (id: string) => pinnedArticles.some(a => a.id === id),
    [pinnedArticles]
  )

  const pinArticles = useCallback((articles: PinnedArticle[]) => {
    setPinnedArticles(prev => {
      const existingIds = new Set(prev.map(a => a.id))
      const toAdd = articles.filter(a => !existingIds.has(a.id))
      return toAdd.length > 0 ? [...prev, ...toAdd] : prev
    })
  }, [])

  const areAllPinned = useCallback(
    (ids: string[]) => ids.length > 0 && ids.every(id => pinnedArticles.some(a => a.id === id)),
    [pinnedArticles]
  )

  const pinGroup = useCallback((group: PinnedGroup) => {
    setPinnedGroups(prev => {
      const existingIds = new Set(prev.map(g => g.id))
      return existingIds.has(group.id)
        ? prev.map(g => (g.id === group.id ? group : g))
        : [...prev, group]
    })
    pinArticles(group.articles)
  }, [pinArticles])

  const toggleGroupArticle = useCallback((groupId: string, articleId: string) => {
    const group = pinnedGroups.find(g => g.id === groupId)
    if (!group) return
    const article = group.articles.find(a => a.id === articleId)
    if (!article) return

    const willBePinned = !isPinned(articleId)
    setPinnedArticles(prev =>
      willBePinned ? [...prev, article] : prev.filter(a => a.id !== articleId)
    )

    const includedAfter = group.articles.filter(a =>
      a.id === articleId ? willBePinned : isPinned(a.id)
    ).length
    if (includedAfter === 0) {
      setPinnedGroups(prev => prev.filter(g => g.id !== groupId))
    }
  }, [pinnedGroups, isPinned])

  const removeGroup = useCallback((groupId: string) => {
    const group = pinnedGroups.find(g => g.id === groupId)
    setPinnedGroups(prev => prev.filter(g => g.id !== groupId))
    if (group) {
      const idsToRemove = new Set(group.articles.map(a => a.id))
      setPinnedArticles(prev => prev.filter(a => !idsToRemove.has(a.id)))
    }
  }, [pinnedGroups])

  return {
    pinnedArticles,
    togglePinnedArticle,
    removePinnedArticle,
    clearPinnedArticles,
    isPinned,
    pinArticles,
    areAllPinned,
    pinnedGroups,
    pinGroup,
    toggleGroupArticle,
    removeGroup,
  }
}

// Per-article pin context — scoped to a single article's chat (FloatingChatbotWrapper,
// article-card.tsx's "pin to chat" toggle). Deliberately a separate context instance from
// PinnedReportContext below so pinning an article for its own chat never leaks into the
// weekly-report chat's pinned set, and vice versa.
const PinnedArticleContext = createContext<PinnedArticleContextValue | null>(null)

export function PinnedArticleProvider({ children }: { children: React.ReactNode }) {
  const store = usePinnedArticleStore()
  return (
    <PinnedArticleContext.Provider value={store}>
      {children}
    </PinnedArticleContext.Provider>
  )
}

export function usePinnedArticle() {
  const ctx = useContext(PinnedArticleContext)
  if (!ctx) throw new Error('usePinnedArticle must be used within PinnedArticleProvider')
  return ctx
}

// Weekly-report pin context — scoped to the weekly-report chat (WeeklyReportWidget,
// InlineQABarWrapper). See PinnedArticleContext above for why this is a separate instance.
const PinnedReportContext = createContext<PinnedArticleContextValue | null>(null)

export function PinnedReportProvider({ children }: { children: React.ReactNode }) {
  const store = usePinnedArticleStore()
  return (
    <PinnedReportContext.Provider value={store}>
      {children}
    </PinnedReportContext.Provider>
  )
}

export function usePinnedReport() {
  const ctx = useContext(PinnedReportContext)
  if (!ctx) throw new Error('usePinnedReport must be used within PinnedReportProvider')
  return ctx
}
