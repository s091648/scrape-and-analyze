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

  return (
    <PinnedArticleContext.Provider value={{
      pinnedArticles,
      togglePinnedArticle,
      removePinnedArticle,
      clearPinnedArticles,
      isPinned,
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
