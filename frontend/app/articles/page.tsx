'use client'

import { Suspense, useEffect, useState, useCallback, useMemo } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import { fetchArticles, type Article } from '@/lib/api/articles'
import { ArticleCard, ArticleCardSkeleton } from '@/components/features/articles/article-card'
import { FilterBar } from '@/components/features/articles/filter-bar'
import { SortSelect } from '@/components/features/articles/sort-select'
import { usePagination } from '@/hooks/use-pagination'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Newspaper, Lock } from 'lucide-react'
import { useTopic, useI18n, useGuestMode } from '@/lib/providers'

const GUEST_PLACEHOLDER_ARTICLES: Article[] = Array.from({ length: 6 }, (_, i) => ({
  id: `guest-${i}`,
  title: 'Lorem ipsum dolor sit amet consectetur adipiscing elit',
  source: 'arxiv',
  content:
    'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor ' +
    'incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud ' +
    'exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.',
  published_at: new Date(Date.now() - i * 86400000).toISOString(),
  scraped_at: null,
  url: '#',
}))

function ArticlesPageContent() {
  const { data: session, status } = useSession()
  const token = (session as { accessToken?: string } | null)?.accessToken
  const { isGuestMode } = useGuestMode()
  const isPaywall = status === 'unauthenticated' && !isGuestMode
  const searchParams = useSearchParams()
  const router = useRouter()
  const { t, locale } = useI18n()
  const {
    page, sort, order, favoritesOnly, setPage, setSort, setOrder, setFilters, setFavoritesOnly,
    aggregators, originalSources, tags, tagGroups,
    publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    activeFilterCount,
  } = usePagination()
  const [articles, setArticles] = useState<Article[]>([])
  const firstVectorArticleId = useMemo(
    () => articles.find(a => a.has_vectors)?.id,
    [articles]
  )
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const { selectedTopicId } = useTopic()
  const [openArticleId, setOpenArticleId] = useState<string | null>(
    () => searchParams.get('article')
  )

  const fetchSearchParamsString = useMemo(() => {
    const p = new URLSearchParams(searchParams.toString())
    p.delete('article')
    // Favorites-only is applied client-side below (see displayedArticles), not re-fetched.
    p.delete('favorites_only')
    return p.toString()
  }, [searchParams])

  const handleArticleOpenChange = useCallback((articleId: string, open: boolean) => {
    setOpenArticleId(open ? articleId : null)
    const params = new URLSearchParams(searchParams.toString())
    if (open) {
      params.set('article', articleId)
    } else {
      params.delete('article')
    }
    router.replace(`/articles?${params.toString()}`, { scroll: false })
  }, [searchParams, router])

  useEffect(() => {
    if (isPaywall) { setIsLoading(false); return }
    if (!selectedTopicId) return
    setIsLoading(true)

    fetchArticles(
      {
        page: isGuestMode ? 1 : page,
        topic_id: selectedTopicId,
        sort,
        order,
        aggregator: aggregators,
        original_source: originalSources,
        tag: tags,
        tag_group: tagGroups,
        published_after: publishedAfter,
        published_before: publishedBefore,
        scraped_after: scrapedAfter,
        scraped_before: scrapedBefore,
      },
      locale,
      token,
    )
      .then(data => { setArticles(data.items); setTotal(data.total) })
      .finally(() => setIsLoading(false))
  }, [fetchSearchParamsString, selectedTopicId, isPaywall, isGuestMode, locale, token])

  // Favorites-only is a display filter over the already-fetched page — toggling it
  // doesn't need a new API round trip, just a re-render.
  const displayedArticles = favoritesOnly ? articles.filter(a => a.is_favorited) : articles

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div className="flex items-center gap-3">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold leading-none">{t('nav.articles')}</h1>
          <span className="inline-flex items-center h-6 px-2.5 rounded-full bg-muted text-xs font-medium text-muted-foreground">
            {favoritesOnly ? displayedArticles.length : total}
          </span>
        </div>
      </div>

      <FilterBar
        aggregators={aggregators}
        originalSources={originalSources}
        tags={tags}
        tagGroups={tagGroups}
        publishedAfter={publishedAfter}
        publishedBefore={publishedBefore}
        scrapedAfter={scrapedAfter}
        scrapedBefore={scrapedBefore}
        activeFilterCount={activeFilterCount}
        favoritesOnly={favoritesOnly}
        onFavoritesToggle={setFavoritesOnly}
        onApply={setFilters}
      >
        <SortSelect sort={sort} order={order} onSortChange={setSort} onOrderChange={setOrder} />
      </FilterBar>

      <div className="relative">
        <div className="grid gap-3 lg:grid-cols-2">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => <ArticleCardSkeleton key={i} />)
            : isPaywall
              ? GUEST_PLACEHOLDER_ARTICLES.map(a => (
                  <div key={a.id} className="select-none pointer-events-none blur-[2px] opacity-70">
                    <ArticleCard {...a} />
                  </div>
                ))
              : displayedArticles.map((a, i) => (
                  <ArticleCard
                    key={a.id}
                    {...a}
                    open={openArticleId === a.id}
                    onOpenChange={(v) => handleArticleOpenChange(a.id, v)}
                    isFirstTutorialTarget={a.id === firstVectorArticleId}
                    isStatsTutorialTarget={i === 0}
                  />
                ))
          }
        </div>

        {!isLoading && isPaywall && (
          <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-background via-background/90 to-transparent flex flex-col items-center justify-end pb-10 gap-4">
            <div className="flex items-center justify-center h-12 w-12 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">{t('home.thereMoreToExplore')}</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">{t('login.signIn')}</Link>
                {' '}{t('home.signInToReadMore')}
              </p>
            </div>
          </div>
        )}
      </div>

      {status === 'authenticated' && !favoritesOnly && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-4 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="rounded-full h-8 px-3 gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            {t('home.previous')}
          </Button>
          {(() => {
            const [before, after] = t('home.pageOf').replace('{total}', String(totalPages)).split('{page}')
            return (
              <span className="flex items-center gap-1 text-sm text-muted-foreground">
                {before}
                <input
                  key={page}
                  type="number"
                  min={1}
                  max={totalPages}
                  defaultValue={page}
                  className="w-12 h-7 text-sm text-center rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const val = parseInt((e.target as HTMLInputElement).value)
                      if (!isNaN(val) && val >= 1 && val <= totalPages) setPage(val)
                    }
                  }}
                />
                {after}
              </span>
            )
          })()}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="rounded-full h-8 px-3 gap-1"
          >
            {t('home.next')}
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}

export default function ArticlesPage() {
  return (
    <Suspense fallback={<div />}>
      <ArticlesPageContent />
    </Suspense>
  )
}
