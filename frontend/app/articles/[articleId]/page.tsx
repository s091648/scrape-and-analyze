'use client'
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useSession } from 'next-auth/react'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleCard, ArticleCardSkeleton } from '@/components/features/articles/article-card'
import { useI18n } from '@/lib/providers'
import { Rss } from 'lucide-react'

export default function ArticleSharePage() {
  const { articleId } = useParams<{ articleId: string }>()
  const searchParams = useSearchParams()
  const topicId = searchParams.get('topic')
  const { locale, t } = useI18n()
  const { status } = useSession()
  const [article, setArticle] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [isGuest, setIsGuest] = useState(false)

  useEffect(() => {
    setIsGuest(sessionStorage.getItem('guest_mode') === 'true')
  }, [])

  useEffect(() => {
    if (!articleId) return
    setNotFound(false)
    setArticle(null)
    setLoading(true)
    fetchArticleById(articleId, locale)
      .then(data => { setArticle(data); setLoading(false) })
      .catch(() => { setNotFound(true); setLoading(false) })
  }, [articleId, locale])

  const appHref = (() => {
    const params = new URLSearchParams()
    if (topicId) params.set('topic', topicId)
    params.set('article', articleId)
    return `/?${params.toString()}`
  })()

  const showPrompt = status !== 'loading'
  const isLoggedInOrGuest = status === 'authenticated' || isGuest

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <Rss className="h-4 w-4" />
          Scrape Analyzer
        </Link>
        {showPrompt && (
          <Link
            href={isLoggedInOrGuest ? appHref : '/login'}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            {isLoggedInOrGuest ? t('share.openInApp') : t('share.signInForMore')}
          </Link>
        )}
      </div>

      {loading && <ArticleCardSkeleton />}

      {!loading && notFound && (
        <div data-testid="article-not-found" className="rounded-2xl border border-border bg-card p-8 text-center space-y-2">
          <p className="text-sm font-medium">{t('share.articleNotFound')}</p>
          <p className="text-sm text-muted-foreground">
            {t('share.articleNotFoundDesc')}
          </p>
          <Link href="/" className="text-sm text-primary underline underline-offset-4">
            {t('share.backToArticles')}
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
