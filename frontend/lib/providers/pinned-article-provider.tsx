'use client'
import { createContext, useContext, useCallback, useState } from 'react'

export interface PinnedArticle {
  id: string
  title: string
  tags?: string[]
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
}

const PinnedArticleContext = createContext<PinnedArticleContextValue | null>(null)

export function PinnedArticleProvider({ children }: { children: React.ReactNode }) {
  const [pinnedArticles, setPinnedArticles] = useState<PinnedArticle[]>([])

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

  return (
    <PinnedArticleContext.Provider value={{
      pinnedArticles,
      togglePinnedArticle,
      removePinnedArticle,
      clearPinnedArticles,
      isPinned,
      pinArticles,
      areAllPinned,
    }}>
      {children}
    </PinnedArticleContext.Provider>
  )
}

export function usePinnedArticle() {
  const ctx = useContext(PinnedArticleContext)
  if (!ctx) throw new Error('usePinnedArticle must be used within PinnedArticleProvider')
  return ctx
}
