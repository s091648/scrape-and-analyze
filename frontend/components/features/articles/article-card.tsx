'use client'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ExternalLink, Clock, Globe } from 'lucide-react'
import { fetchArticleById, type Article } from '@/lib/api/articles'
import { ArticleCardSkeleton } from './article-card-skeleton'
import { ArticleDetailDialog } from './article-detail-dialog'
import { useI18n } from '@/lib/providers'
import type { ArticleDetail } from '@/lib/api/articles'

export type { Article }

export function ArticleCard({ id, title, source, content, published_at, scraped_at, url }: Article) {
  const { locale } = useI18n()
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    fetchArticleById(id, locale)
      .then(data => { setDetail(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [open, locale, id])

  return (
    <>
      <Card
        className="group rounded-2xl border border-border bg-card hover:bg-muted/40 transition-colors duration-200 overflow-hidden cursor-pointer"
        onClick={() => setOpen(true)}
      >
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold leading-snug">
            <div className="flex items-start gap-2">
              <span className="flex-1">{title}</span>
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                onClick={e => e.stopPropagation()}
                className="shrink-0 mt-0.5"
              >
                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
              </a>
            </div>
          </CardTitle>
        </CardHeader>

        <div className="relative px-6 h-[4.5rem] overflow-hidden">
          <p className="text-xs text-muted-foreground leading-relaxed">{content}</p>
          <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-card to-transparent pointer-events-none" />
        </div>

        <CardContent className="pt-0 border-t border-border mt-3">
          <div className="flex flex-wrap items-center gap-2 pt-3">
            <span className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs font-medium text-muted-foreground">
              <Globe className="h-3 w-3" />
              {source}
            </span>
            {published_at && (
              <span className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {new Date(published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            )}
            {scraped_at && (
              <span className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs text-muted-foreground">
                Scraped {new Date(scraped_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <ArticleDetailDialog
        open={open}
        onOpenChange={setOpen}
        title={title}
        source={source}
        published_at={published_at}
        content={content}
        detail={detail}
        loading={loading}
      />
    </>
  )
}

export { ArticleCardSkeleton } from './article-card-skeleton'
