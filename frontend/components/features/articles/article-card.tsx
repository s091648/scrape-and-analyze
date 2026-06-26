'use client'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ExternalLink, Clock, Globe, Share2, Check, Download, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { fetchArticleById, type Article } from '@/lib/api/articles'
import { ArticleCardSkeleton } from './article-card-skeleton'
import { ArticleDetailDialog } from './article-detail-dialog'
import { useI18n, useTopic, usePinnedArticle } from '@/lib/providers'
import type { ArticleDetail } from '@/lib/api/articles'

export type { Article }

import { deriveDisplaySource, formatViaSource, toTitleCase } from './source-utils'

interface ArticleCardProps extends Article {
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function ArticleCard({ id, title, source, via_source, original_source, content, published_at, scraped_at, url, translated_title, translated_content, has_vectors, open: controlledOpen, onOpenChange: controlledOnOpenChange }: ArticleCardProps) {
  const { locale, t } = useI18n()
  const { selectedTopicId } = useTopic()
  const { togglePinnedArticle, removePinnedArticle, isPinned } = usePinnedArticle()
  const isControlled = controlledOpen !== undefined
  const [internalOpen, setInternalOpen] = useState(false)
  const open = isControlled ? controlledOpen! : internalOpen
  const setOpen = isControlled
    ? (v: boolean) => controlledOnOpenChange?.(v)
    : setInternalOpen
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  async function handleTogglePin(e: React.MouseEvent) {
    e.stopPropagation()
    if (isPinned(id)) {
      removePinnedArticle(id)
    } else {
      let tags: string[] = []
      if (detail?.tags) {
        tags = detail.tags
      } else {
        try {
          const fetched = await fetchArticleById(id, locale)
          tags = fetched.tags || []
        } catch {}
      }
      togglePinnedArticle({ id, title: displayTitle, tags })
    }
  }

  const displayTitle = translated_title ?? title
  const displayContent = translated_content ?? content
  const displaySource = deriveDisplaySource(url, source, original_source)

  async function handleShare(e: React.MouseEvent) {
    e.stopPropagation()
    const params = new URLSearchParams()
    if (selectedTopicId) params.set('topic', selectedTopicId)
    const shareUrl = `${window.location.origin}/articles/${id}${params.size ? `?${params}` : ''}`
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      toast.success(t('copy.success'))
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('copy.failed'))
    }
  }

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
              <span className="flex-1">{toTitleCase(displayTitle)}</span>
              <div className="flex items-center gap-2 shrink-0 mt-0.5">
                <button
                  type="button"
                  onClick={handleShare}
                  aria-label={t('copy.shareArticle')}
                  className="p-0.5 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                >
                  {copied
                    ? <Check className="h-3.5 w-3.5 text-green-500" />
                    : <Share2 className="h-3.5 w-3.5 text-muted-foreground" />
                  }
                </button>
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  className="cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                >
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </a>
              </div>
            </div>
          </CardTitle>
        </CardHeader>

        <div className="relative px-6 h-[4.5rem] overflow-hidden">
          <p className="text-xs text-muted-foreground leading-relaxed">{displayContent}</p>
          <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-card to-transparent pointer-events-none" />
        </div>

        <CardContent className="pt-0 border-t border-border mt-3">
          <div className="flex items-center justify-between gap-2 pt-3">
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                onClick={e => e.stopPropagation()}
                className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs font-medium text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
              >
                <Globe className="h-3 w-3" />
                {displaySource}
              </a>
              {published_at && (
                <span className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {new Date(published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </span>
              )}
              {scraped_at && (
                <span className="inline-flex items-center gap-1 h-6 px-2.5 rounded-full border border-border bg-background text-xs text-muted-foreground">
                  <Download className="h-3 w-3" />
                  {new Date(scraped_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              {via_source && (
                <span className="inline-flex items-center h-5 px-2 rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
                  {formatViaSource(via_source)}
                </span>
              )}
              {has_vectors && (
                <button
                  type="button"
                  onClick={handleTogglePin}
                  aria-label={isPinned(id) ? t('rag.removeFromChat') : t('rag.addToChat')}
                  title={isPinned(id) ? t('rag.removeFromChat') : t('rag.addToChat')}
                  className={`inline-flex items-center justify-center h-5 w-5 rounded-full cursor-pointer transition-colors ${
                    isPinned(id)
                      ? 'bg-purple-100 dark:bg-purple-900/40'
                      : 'hover:bg-purple-100 dark:hover:bg-purple-900/40'
                  }`}
                >
                  <Sparkles className={`h-3 w-3 transition-colors ${
                    isPinned(id) ? 'text-purple-600 dark:text-purple-400' : 'text-purple-400'
                  }`} />
                </button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <ArticleDetailDialog
        open={open}
        onOpenChange={setOpen}
        title={displayTitle}
        source={source}
        url={url}
        via_source={via_source}
        original_source={original_source}
        published_at={published_at}
        content={displayContent}
        detail={detail}
        loading={loading}
      />
    </>
  )
}

export { ArticleCardSkeleton } from './article-card-skeleton'
