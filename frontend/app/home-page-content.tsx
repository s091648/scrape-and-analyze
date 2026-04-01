'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import { apiFetch } from '@/lib/api-fetch'
import { ArticleCard, ArticleCardSkeleton } from '@/components/article-card'
import { FilterBar } from '@/components/filter-bar'
import { usePagination } from '@/hooks/use-pagination'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Newspaper, Lock } from 'lucide-react'

interface Article {
  id: string; title: string; source: string; content: string
  published_at: string | null; scraped_at: string | null; url: string
}

const GUEST_LIMIT = 6

export default function HomePageContent() {
  const { status } = useSession()
  const isGuest = status === 'unauthenticated'
  const searchParams = useSearchParams()
  const {
    page, sort, order, setPage, setFilters,
    sources, tags, publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    activeFilterCount,
  } = usePagination()
  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)

  const searchParamsString = searchParams.toString()

  useEffect(() => {
    setIsLoading(true)
    apiFetch(`/articles?${searchParamsString}`)
      .then(r => r.json())
      .then(data => { setArticles(data.items); setTotal(data.total) })
      .finally(() => setIsLoading(false))
  }, [searchParamsString])

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-6">
        <div className="flex items-center gap-3">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold leading-none">Articles</h1>
          <span className="inline-flex items-center h-6 px-2.5 rounded-full bg-muted text-xs font-medium text-muted-foreground">
            {total}
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar
        sources={sources}
        tags={tags}
        publishedAfter={publishedAfter}
        publishedBefore={publishedBefore}
        scrapedAfter={scrapedAfter}
        scrapedBefore={scrapedBefore}
        activeFilterCount={activeFilterCount}
        onApply={setFilters}
      />

      {/* Grid */}
      <div className="relative">
        <div className="grid gap-3 lg:grid-cols-2">
          {isLoading
            ? Array.from({ length: 6 }).map((_, i) => <ArticleCardSkeleton key={i} />)
            : (isGuest ? articles.slice(0, GUEST_LIMIT) : articles).map(a => <ArticleCard key={a.id} {...a} />)
          }
        </div>

        {/* Guest paywall overlay — only show when not loading and has articles */}
        {!isLoading && isGuest && articles.length > 0 && (
          <div className="absolute bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-background via-background/90 to-transparent flex flex-col items-center justify-end pb-10 gap-4">
            <div className="flex items-center justify-center h-12 w-12 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">There&apos;s more to explore</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">Sign in</Link>
                {' '}to read more articles
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Pagination — hidden for guests */}
      {!isGuest && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-4 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1}
            className="rounded-full h-8 px-3 gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page <span className="font-medium text-foreground">{page}</span> of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages}
            className="rounded-full h-8 px-3 gap-1"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  )
}