'use client'
import { useState } from 'react'
import { Eye, Pencil, Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'
import type { TagGroupOut, TagOut } from '@/lib/api/tags'
import { deleteTagGroup } from '@/lib/api/tags'
import { TagDialog } from './tag-dialog'

interface Props {
  group: TagGroupOut
  isAdmin: boolean
  token?: string
  onDeleted: (groupId: string) => void
  onTagRenamed: (groupId: string, tagId: string, newName: string) => void
  onTagDeleted: (groupId: string, tagId: string) => void
}

function TagBadge({
  tag,
  isAdmin,
  token,
  topicId,
  onRenamed,
  onDeleted,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  topicId: string
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)

  return (
    <>
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-muted/50 text-xs">
        {tag.name}
        <span className="text-muted-foreground tabular-nums [font-variant-ligatures:none]">
          ({tag.article_count})
        </span>
        <button
          onClick={() => setOpen(true)}
          className="hover:text-foreground text-muted-foreground"
          aria-label={isAdmin ? t('tags.renameTag') : t('tags.viewTagArticles')}
        >
          {isAdmin
            ? <Pencil className="h-2.5 w-2.5" />
            : <Eye className="h-2.5 w-2.5" />
          }
        </button>
      </span>

      <TagDialog
        tag={tag}
        topicId={topicId}
        isAdmin={isAdmin}
        token={token}
        open={open}
        onOpenChange={setOpen}
        onRenamed={onRenamed}
        onDeleted={onDeleted}
      />
    </>
  )
}

export function TagGroupCard({ group, isAdmin, token, onDeleted, onTagRenamed, onTagDeleted }: Props) {
  const { t } = useI18n()
  const [tags, setTags] = useState<TagOut[]>(
    [...group.tags].sort((a, b) => b.article_count - a.article_count)
  )
  const [open, setOpen] = useState(true)

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <button
          className="flex items-center gap-2 flex-1 min-w-0 text-left"
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
        >
          {group.color_hex && (
            <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: group.color_hex }} />
          )}
          <span className="font-semibold text-sm">{group.display_name}</span>
          <span className="text-xs text-muted-foreground">{t('tags.tagsCount', { count: tags.length })}</span>
          {open
            ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          }
        </button>
        {isAdmin && token && (
          <Button
            variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive shrink-0"
            onClick={async () => { await deleteTagGroup(group.id, token); onDeleted(group.id) }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {open && (
        <>
          {group.description && (
            <p className="text-xs text-muted-foreground">{group.description}</p>
          )}
          <div className="flex flex-wrap gap-1.5">
            {tags.map(tag => (
              <TagBadge
                key={tag.id}
                tag={tag}
                isAdmin={isAdmin}
                token={token}
                topicId={String(group.topic_id)}
                onRenamed={(tagId, name) => {
                  setTags(prev => prev.map(t => t.id === tagId ? { ...t, name } : t))
                  onTagRenamed(group.id, tagId, name)
                }}
                onDeleted={tagId => {
                  setTags(prev => prev.filter(t => t.id !== tagId))
                  onTagDeleted(group.id, tagId)
                }}
              />
            ))}
            {tags.length === 0 && (
              <span className="text-xs text-muted-foreground italic">{t('tags.noTagsYet')}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
