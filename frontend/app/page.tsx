'use client'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { apiFetch } from '@/lib/api-fetch'
import { ArticleCard } from '@/components/article-card'
import { FilterBar } from '@/components/filter-bar'
import { usePagination } from '@/hooks/use-pagination'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Newspaper } from 'lucide-react'

interface Article {
  id: string; title: string; source: string; content: string
  published_at: string | null; scraped_at: string | null; url: string
}

export default function HomePage() {
  const searchParams = useSearchParams()
  const {
    page, sort, order, setPage, setFilters,
    sources, tags, publishedAfter, publishedBefore, scrapedAfter, scrapedBefore,
    activeFilterCount,
  } = usePagination()
  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)

  const searchParamsString = searchParams.toString()

  useEffect(() => {
    apiFetch(`/articles?${searchParamsString}`)
      .then(r => r.json())
      .then(data => { setArticles(data.items); setTotal(data.total) })
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
      <div className="grid gap-3 lg:grid-cols-2">
        {articles.map(a => <ArticleCard key={a.id} {...a} />)}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
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
