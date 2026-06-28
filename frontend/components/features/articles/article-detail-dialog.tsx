'use client'
import { useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Clock, ExternalLink, Globe, Sparkles, Quote, Eye } from 'lucide-react'
import { ArticleDetail, recordArticleView } from '@/lib/api/articles'
import { ArticleDetailSkeleton } from './article-card-skeleton'
import { useI18n } from '@/lib/providers'

import { deriveDisplaySource, formatViaSource } from './source-utils'

interface ArticleDetailDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  id: string
  title: string
  source: string
  url: string
  via_source?: string | null
  original_source?: string | null
  published_at: string | null
  content: string
  detail: ArticleDetail | null
  loading: boolean
}

export function ArticleDetailDialog({
  open, onOpenChange, id, title, source, url, via_source, original_source, published_at, content, detail, loading,
}: ArticleDetailDialogProps) {
  const { t, locale } = useI18n()
  const hasAnalysis = detail && !!detail.model_used

  useEffect(() => {
    if (open) recordArticleView(id)
  }, [open, id])
  const displaySource = deriveDisplaySource(url, source, original_source)
  const displayTitle = detail?.translated_title ?? title
  const displayContent = detail?.translated_content ?? detail?.content ?? content

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
          <DialogTitle className="text-lg leading-snug pr-6">
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-start gap-2 hover:underline cursor-pointer"
              onClick={e => e.stopPropagation()}
            >
              {displayTitle}
              <ExternalLink className="h-4 w-4 shrink-0 mt-0.5 text-muted-foreground" />
            </a>
          </DialogTitle>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Globe className="h-3 w-3" />{displaySource}
            </span>
            {via_source && (
              <span className="inline-flex items-center h-5 px-2 rounded-full bg-muted text-[10px] font-medium text-muted-foreground">
                {formatViaSource(via_source)}
              </span>
            )}
            {published_at && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {new Date(published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            )}
            {detail?.citation_count != null && detail.citation_count > 0 && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Quote className="h-3 w-3" />
                {detail.citation_count.toLocaleString()} citations
              </span>
            )}
            {detail?.view_count != null && detail.view_count > 0 && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Eye className="h-3 w-3" />
                {detail.view_count.toLocaleString()} views
              </span>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
          {loading ? (
            <ArticleDetailSkeleton />
          ) : (
            <div className="space-y-6">
              <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                {displayContent}
              </p>
              {locale !== 'en' && (!!detail?.translated_content || !!detail?.translated_title) && (
                <p className="text-xs text-muted-foreground italic mt-2">
                  {t('analysis.translationDisclaimer')}
                </p>
              )}

              {detail && !hasAnalysis && (
                <div className="border border-dashed border-border rounded-xl p-4 text-center">
                  <Sparkles className="h-5 w-5 mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground mb-3">No analysis available yet.</p>
                  <Button variant="outline" size="sm" disabled>Create Analysis</Button>
                </div>
              )}

              {hasAnalysis && (
                <div className="space-y-4 border-t border-border pt-4">
                  {detail.tag_groups.length > 0 && (
                    <div className="space-y-2">
                      {detail.tag_groups.map(group => (
                        <div key={group.group_name}>
                          <span
                            className="text-[10px] font-semibold uppercase tracking-wide"
                            style={{ color: group.color || 'hsl(var(--muted-foreground))' }}
                          >
                            {group.display_name}
                          </span>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {group.tags.map(tag => (
                              <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {detail.pain_points && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">{t('analysis.painPoints')}</h4>
                      <p className="text-sm text-foreground leading-relaxed">{detail.pain_points}</p>
                    </div>
                  )}
                  {detail.insights && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">{t('analysis.insights')}</h4>
                      <p className="text-sm text-foreground leading-relaxed">{detail.insights}</p>
                    </div>
                  )}
                  {detail.innovations && (
                    <div>
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">{t('analysis.innovations')}</h4>
                      <p className="text-sm text-foreground leading-relaxed">{detail.innovations}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
