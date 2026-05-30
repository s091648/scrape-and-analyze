'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleCard, ArticleCardSkeleton } from '@/components/features/articles/article-card'
import { useI18n } from '@/lib/providers'
import { Rss } from 'lucide-react'

export default function ArticleSharePage() {
  const { articleId } = useParams<{ articleId: string }>()
  const { locale } = useI18n()
  const [article, setArticle] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!articleId) return
    setLoading(true)
    fetchArticleById(articleId, locale)
      .then(data => { setArticle(data); setLoading(false) })
      .catch(() => { setNotFound(true); setLoading(false) })
  }, [articleId, locale])

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link href="/" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <Rss className="h-4 w-4" />
          Scrape Analyzer
        </Link>
      </div>

      {loading && <ArticleCardSkeleton />}

      {!loading && notFound && (
        <div className="rounded-2xl border border-border bg-card p-8 text-center space-y-2">
          <p className="text-sm font-medium">Article not found</p>
          <p className="text-sm text-muted-foreground">
            This article may have been removed or the link is invalid.
          </p>
          <Link href="/" className="text-sm text-primary underline underline-offset-4">
            Back to articles
          </Link>
        </div>
      )}

      {!loading && article && (
        <ArticleCard
          id={article.id}
          title={article.title}
          source={article.source}
          content={article.content}
          published_at={article.published_at}
          scraped_at={article.scraped_at}
          url={article.url}
        />
      )}
    </div>
  )
}
