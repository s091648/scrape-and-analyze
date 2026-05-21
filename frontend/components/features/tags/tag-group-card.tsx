'use client'
import { useState, useEffect, useRef } from 'react'
import { Pencil, Trash2, ChevronDown, ChevronUp, Check, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'
import type { TagGroupOut, TagOut, TagGroupUpdate } from '@/lib/api/tags'
import { deleteTagGroup, updateTagGroup } from '@/lib/api/tags'
import { TagDialog } from './tag-dialog'
import { useDraggable, useDroppable } from '@dnd-kit/core'
import { cn } from '@/lib/utils'

interface Props {
  group: TagGroupOut
  isAdmin: boolean
  token?: string
  pendingIncomingTagIds: Set<string>
  onDeleted: (groupId: string) => void
  onTagRenamed: (groupId: string, tagId: string, newName: string) => void
  onTagDeleted: (groupId: string, tagId: string) => void
  onGroupUpdated: (groupId: string, updated: Partial<TagGroupOut>) => void
}

function TagBadge({
  tag,
  isAdmin,
  token,
  topicId,
  groupId,
  isPending,
  onRenamed,
  onDeleted,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  topicId: string
  groupId: string
  isPending: boolean
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
}) {
  const [open, setOpen] = useState(false)

  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: tag.id,
    data: { groupId, tag },
    disabled: !isAdmin,
  })

  return (
    <>
      <button
        ref={setNodeRef}
        {...listeners}
        {...attributes}
        onClick={() => setOpen(true)}
        data-pending-change={isPending ? tag.id : undefined}
        className={cn(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs transition-colors',
          isPending
            ? 'border-green-400 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 animate-wiggle'
            : 'border-border bg-muted/50 hover:bg-muted cursor-pointer',
          isDragging && 'opacity-40',
          isAdmin && 'cursor-grab active:cursor-grabbing',
        )}
      >
        {tag.name}
        <span className="text-muted-foreground tabular-nums [font-variant-ligatures:none]">
          ({tag.article_count})
        </span>
      </button>

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

function EditGroupForm({
  group,
  token,
  onSaved,
  onCancel,
}: {
  group: TagGroupOut
  token: string
  onSaved: (updated: Partial<TagGroupOut>) => void
  onCancel: () => void
}) {
  const { t } = useI18n()
  const [form, setForm] = useState<TagGroupUpdate>({
    display_name: group.display_name,
    color_hex: group.color_hex ?? '',
    description: group.description ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.display_name?.trim()) return
    setSaving(true)
    setError('')
    try {
      const body: TagGroupUpdate = {
        display_name: form.display_name.trim(),
        ...(form.color_hex?.trim() ? { color_hex: form.color_hex.trim() } : { color_hex: undefined }),
        ...(form.description?.trim() ? { description: form.description.trim() } : { description: undefined }),
      }
      const updated = await updateTagGroup(group.id, body, token)
      onSaved({ display_name: updated.display_name, color_hex: updated.color_hex, description: updated.description })
    } catch (err: any) {
      setError(err.message ?? 'Error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="pt-2 space-y-3 border-t border-border">
      {[
        { key: 'display_name', label: t('tags.groupDisplayName'), required: true },
        { key: 'color_hex', label: t('tags.groupColor'), required: false, placeholder: '#3b82f6' },
        { key: 'description', label: t('tags.groupDescription'), required: false },
      ].map(({ key, label, required, placeholder }) => (
        <div key={key} className="space-y-1">
          <label className="text-xs text-muted-foreground">{label}{required && ' *'}</label>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            value={(form as any)[key] ?? ''}
            placeholder={placeholder}
            onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
            required={required}
          />
        </div>
      ))}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          <X className="h-3.5 w-3.5 mr-1" />{t('admin.cancel')}
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          <Check className="h-3.5 w-3.5 mr-1" />{t('admin.save')}
        </Button>
      </div>
    </form>
  )
}

export function TagGroupCard({
  group, isAdmin, token, pendingIncomingTagIds,
  onDeleted, onTagRenamed, onTagDeleted, onGroupUpdated,
}: Props) {
  const { t } = useI18n()
  const [tags, setTags] = useState<TagOut[]>(
    [...group.tags].sort((a, b) => b.article_count - a.article_count)
  )
  const [open, setOpen] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const [hasOverflow, setHasOverflow] = useState(false)
  const [editing, setEditing] = useState(false)
  const [localGroup, setLocalGroup] = useState(group)
  const tagContainerRef = useRef<HTMLDivElement>(null)

  const tagIdsKey = group.tags.map(t => t.id).join(',')
  useEffect(() => {
    setTags([...group.tags].sort((a, b) => b.article_count - a.article_count))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tagIdsKey])

  useEffect(() => {
    if (!open || expanded) { setHasOverflow(false); return }
    const el = tagContainerRef.current
    if (!el) return
    const id = requestAnimationFrame(() => {
      setHasOverflow(el.scrollHeight > el.clientHeight)
    })
    return () => cancelAnimationFrame(id)
  }, [tags, open, expanded])

  const { setNodeRef, isOver } = useDroppable({ id: group.id })

  function handleGroupSaved(updated: Partial<TagGroupOut>) {
    const next = { ...localGroup, ...updated }
    setLocalGroup(next)
    onGroupUpdated(group.id, updated)
    setEditing(false)
  }

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'rounded-xl border border-border bg-card p-5 space-y-3 transition-colors',
        isOver && 'border-primary/50 bg-primary/5',
      )}
    >
      <div className="flex items-center justify-between">
        <button
          className="flex items-center gap-2 flex-1 min-w-0 text-left"
          onClick={() => setOpen(o => !o)}
          aria-expanded={open}
        >
          {localGroup.color_hex && (
            <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: localGroup.color_hex }} />
          )}
          <span className="font-semibold text-sm">{localGroup.display_name}</span>
          <span className="text-xs text-muted-foreground">{t('tags.tagsCount', { count: tags.length })}</span>
          {open
            ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          }
        </button>
        {isAdmin && token && (
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={() => setEditing(e => !e)}
              aria-label={t('tags.editGroup')}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={async () => { await deleteTagGroup(group.id, token); onDeleted(group.id) }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>

      {isAdmin && token && editing && (
        <EditGroupForm
          group={localGroup}
          token={token}
          onSaved={handleGroupSaved}
          onCancel={() => setEditing(false)}
        />
      )}

      {open && (
        <>
          {localGroup.description && (
            <p className="text-xs text-muted-foreground">{localGroup.description}</p>
          )}
          <div className="relative">
            <div
              ref={tagContainerRef}
              className={cn(
                'flex flex-wrap gap-1.5 overflow-hidden',
                !expanded && 'max-h-28',
              )}
            >
              {tags.map(tag => (
                <TagBadge
                  key={tag.id}
                  tag={tag}
                  isAdmin={isAdmin}
                  token={token}
                  topicId={String(localGroup.topic_id)}
                  groupId={String(group.id)}
                  isPending={pendingIncomingTagIds.has(tag.id)}
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
            {!expanded && hasOverflow && (
              <div className="absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-card to-transparent flex items-end justify-center pb-2">
                <button
                  onClick={() => setExpanded(true)}
                  className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t('tags.expand')}
                </button>
              </div>
            )}
          </div>
          {expanded && (
            <button
              onClick={() => setExpanded(false)}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {t('tags.collapse')}
            </button>
          )}
        </>
      )}
    </div>
  )
}
