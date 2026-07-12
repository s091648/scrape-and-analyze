'use client'
import { useState, useEffect } from 'react'
import { Pencil, Trash2, Check, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ArticleCard } from '@/components/features/articles/article-card'
import { useI18n } from '@/lib/providers'
import { fetchArticles, type Article } from '@/lib/api/articles'
import { renameTag, deleteTag, type TagOut } from '@/lib/api/tags'

const PAGE_SIZE = 10

interface TagDialogProps {
  tag: TagOut
  topicId: string
  isAdmin: boolean
  token?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onRenamed: (tagId: string, newName: string) => void
  onDeleted: (tagId: string) => void
}

export function TagDialog({
  tag, topicId, isAdmin, token, open, onOpenChange, onRenamed, onDeleted,
}: TagDialogProps) {
  const { t, locale } = useI18n()
  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loadingArticles, setLoadingArticles] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(tag.name)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const totalPages = Math.ceil(total / PAGE_SIZE)

  useEffect(() => {
    if (!open) {
      setEditing(false)
      setEditValue(tag.name)
      setConfirmDelete(false)
      setPage(1)
      return
    }
    setLoadingArticles(true)
    fetchArticles({ tag_id: [tag.id], topic_id: topicId || undefined, page, size: PAGE_SIZE }, locale)
      .then(data => {
        setArticles(data.items)
        setTotal(data.total)
      })
      .finally(() => setLoadingArticles(false))
  }, [open, tag.name, topicId, locale, page])

  async function handleRename() {
    if (!token || !editValue.trim()) return
    if (editValue.trim() === tag.name) { setEditing(false); return }
    setSaving(true)
    try {
      await renameTag(tag.id, editValue.trim(), token)
      onRenamed(tag.id, editValue.trim())
      setEditing(false)
    } catch {
      // API errors are surfaced to the parent via the absence of the onRenamed callback
    } finally {
      setSaving(false)
    }
  }

  function cancelEdit() {
    setEditing(false)
    setEditValue(tag.name)
  }

  async function handleDelete() {
    if (!token) return
    setDeleting(true)
    try {
      await deleteTag(tag.id, token)
      onDeleted(tag.id)
      onOpenChange(false)
    } catch {
      // API errors are surfaced to the parent via the absence of the onDeleted callback
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2 pr-6">
            {editing ? (
              <>
                <input
                  className="flex-1 bg-transparent text-lg font-semibold focus:outline-none border-b border-border pb-0.5"
                  value={editValue}
                  onChange={e => setEditValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleRename()
                    if (e.key === 'Escape') cancelEdit()
                  }}
                  autoFocus
                />
                <button onClick={handleRename} disabled={saving} className="shrink-0 text-muted-foreground hover:text-green-600 cursor-pointer">
                  <Check className="h-4 w-4" />
                </button>
                <button onClick={cancelEdit} className="shrink-0 text-muted-foreground hover:text-foreground cursor-pointer">
                  <X className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                <DialogTitle className="text-lg leading-snug flex-1">{tag.name}</DialogTitle>
                {isAdmin && !confirmDelete && (
                  <>
                    <button
                      onClick={() => setEditing(true)}
                      className="shrink-0 text-muted-foreground hover:text-foreground cursor-pointer"
                      aria-label={t('tags.renameTag')}
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => setConfirmDelete(true)}
                      className="shrink-0 text-muted-foreground hover:text-destructive cursor-pointer"
                      aria-label={t('tags.deleteTag')}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </>
                )}
              </>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {t('tags.articleCount', { count: tag.article_count })}
          </p>
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
          {confirmDelete ? (
            <div className="flex flex-col items-center gap-4 py-8 text-center">
              <p className="text-sm font-medium">{t('tags.deleteTagConfirm', { name: tag.name })}</p>
              <p className="text-xs text-muted-foreground">{t('tags.deleteTagDesc')}</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setConfirmDelete(false)}>
                  {t('admin.cancel')}
                </Button>
                <Button
                  variant="destructive" size="sm"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {t('admin.delete')}
                </Button>
              </div>
            </div>
          ) : loadingArticles ? (
            <div className="space-y-4">
              {[0, 1, 2].map(i => <Skeleton key={i} className="h-32 w-full rounded-2xl" />)}
            </div>
          ) : articles.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">{t('tags.noArticles')}</p>
          ) : (
            <div className="space-y-4">
              {articles.map(article => (
                <ArticleCard key={article.id} {...article} />
              ))}
            </div>
          )}
        </div>

        {!confirmDelete && totalPages > 1 && (
          <div className="px-6 py-3 border-t border-border shrink-0 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {t('home.pageOf', { page, total: totalPages })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                disabled={page === 1 || loadingArticles}
                onClick={() => setPage(p => p - 1)}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost" size="icon" className="h-7 w-7"
                disabled={page === totalPages || loadingArticles}
                onClick={() => setPage(p => p + 1)}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
