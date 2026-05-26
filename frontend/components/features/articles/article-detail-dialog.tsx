'use client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Clock, Globe, Sparkles } from 'lucide-react'
import { ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailSkeleton } from './article-card-skeleton'
import { useI18n } from '@/lib/providers'

interface ArticleDetailDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  source: string
  published_at: string | null
  content: string
  detail: ArticleDetail | null
  loading: boolean
}

export function ArticleDetailDialog({
  open, onOpenChange, title, source, published_at, content, detail, loading,
}: ArticleDetailDialogProps) {
  const { t } = useI18n()
  const hasAnalysis = detail && !!detail.model_used

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
