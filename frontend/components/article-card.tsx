'use client'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ExternalLink, Clock, Globe, Sparkles } from 'lucide-react'
import { apiFetch } from '@/lib/api-fetch'
import { Skeleton } from '@/components/ui/skeleton'
import { useI18n } from '@/i18n'

interface ArticleCardProps {
  id: string
  title: string
  source: string
  content: string
  published_at: string | null
  scraped_at: string | null
  url: string
}

interface TagGroup {
  group_name: string
  display_name: string
  color: string
  tags: string[]
}

interface ArticleDetail {
  id: string
  url: string
  source: string
  title: string
  content: string
  published_at: string | null
  scraped_at: string | null
  tags: string[]
  tag_groups: TagGroup[]
  pain_points: string | null
  insights: string | null
  innovations: string | null
  model_used: string | null
}

export function ArticleCard({ id, title, source, content, published_at, scraped_at, url }: ArticleCardProps) {
  const { t, locale } = useI18n()
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<ArticleDetail | null>(null)
  const [loading, setLoading] = useState(false)

  // Simple client-side translation for title and content
  const translatedTitle = locale === 'zh-TW' && detail ? translateTitle(detail.title, locale) : title
  const translatedContent = locale === 'zh-TW' && detail ? translateContent(detail.content, locale) : content

  function translateTitle(title: string, lang: string): string {
    // For demo purposes, just return original - in production you'd call a translation API
    return title
  }

  function translateContent(content: string, lang: string): string {
    // For demo purposes, just return original
    return content
  }

  // Fetch article detail when modal opens or locale changes
  useEffect(() => {
    if (!open) return
    setLoading(true)
    apiFetch(`/articles/${id}`, {}, true)
      .then(r => r.json())
      .then(data => { setDetail(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [open, locale])

  function handleCardClick() {
    setOpen(true)
  }

  const hasAnalysis = detail && !!detail.model_used

  return (
    <>
      <Card
        className="group rounded-2xl border border-border bg-card hover:bg-muted/40 transition-colors duration-200 overflow-hidden cursor-pointer"
        onClick={handleCardClick}
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

        {/* Content preview with fade */}
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

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
            <DialogTitle className="text-lg leading-snug pr-6">{title}</DialogTitle>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Globe className="h-3 w-3" />{source}
              </span>
              {published_at && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {new Date(published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
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
                  {detail?.content ?? content}
                </p>

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
                              style={{ color: group.color }}
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
    </>
  )
}

export function ArticleCardSkeleton() {
  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden p-6 space-y-4">
      <Skeleton className="h-5 w-4/5" />
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/5" />
      </div>
      <div className="flex gap-2 pt-2 border-t border-border">
        <Skeleton className="h-6 w-20 rounded-full" />
        <Skeleton className="h-6 w-24 rounded-full" />
      </div>
    </div>
  )
}

export function ArticleDetailSkeleton() {
  return (
    <div className="space-y-6 py-2">
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="space-y-4 border-t border-border pt-4">
        {[0, 1, 2].map(i => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {[0, 1, 2, 3].map(i => (
            <Skeleton key={i} className="h-5 w-16 rounded-full" />
          ))}
        </div>
      </div>
    </div>
  )
}
