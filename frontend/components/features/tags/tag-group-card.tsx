'use client'
import { useState, useEffect, useRef } from 'react'
import { Pencil, Trash2, ChevronDown, ChevronUp, Check, X, GripVertical, GitMerge } from 'lucide-react'
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
  isMergeMode?: boolean
  isMergeSource?: boolean
  isGroupDragActive?: boolean
  showTopInsert?: boolean
  showBottomInsert?: boolean
  selectedTagIds?: Set<string>
  onDeleted: (groupId: string) => void
  onTagRenamed: (groupId: string, tagId: string, newName: string) => void
  onTagDeleted: (groupId: string, tagId: string) => void
  onGroupUpdated: (groupId: string, updated: Partial<TagGroupOut>) => void
  onMergeRequested?: (groupId: string) => void
  onMergeTargetSelected?: (groupId: string) => void
  onTagSelectionToggle?: (tagId: string) => void
}

function TagBadge({
  tag,
  isAdmin,
  token,
  topicId,
  groupId,
  isPending,
  isSelected,
  onRenamed,
  onDeleted,
  onSelectionToggle,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  topicId: string
  groupId: string
  isPending: boolean
  isSelected: boolean
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
  onSelectionToggle: () => void
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
        onClick={(e) => {
          if (isAdmin && (e.ctrlKey || e.metaKey)) {
            e.preventDefault()
            onSelectionToggle()
            return
          }
          setOpen(true)
        }}
        data-pending-change={isPending ? tag.id : undefined}
        className={cn(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs transition-colors',
          isPending
            ? 'border-green-400 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 animate-wiggle'
            : isSelected
            ? 'border-primary bg-primary/10 text-primary ring-1 ring-primary/40'
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
    name: group.name,
    display_name: group.display_name,
    color_hex: group.color_hex ?? '',
    description: group.description ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.display_name?.trim() || !form.name?.trim()) return
    setSaving(true)
    setError('')
    try {
      const body: TagGroupUpdate = {
        name: form.name.trim(),
        display_name: form.display_name.trim(),
        ...(form.color_hex?.trim() ? { color_hex: form.color_hex.trim() } : { color_hex: undefined }),
        ...(form.description?.trim() ? { description: form.description.trim() } : { description: undefined }),
      }
      const updated = await updateTagGroup(group.id, body, token)
      onSaved({ name: updated.name, display_name: updated.display_name, color_hex: updated.color_hex, description: updated.description })
    } catch (err: any) {
      setError(err.message ?? 'Error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="pt-2 space-y-3 border-t border-border">
      {[
        { key: 'name', label: t('tags.groupName'), required: true, hint: 'snake_case (e.g. machine_learning)' },
        { key: 'display_name', label: t('tags.groupDisplayName'), required: true, hint: 'Pascal Case with spaces (e.g. Machine Learning)' },
        { key: 'color_hex', label: t('tags.groupColor'), required: false, placeholder: '#3b82f6' },
        { key: 'description', label: t('tags.groupDescription'), required: false },
      ].map(({ key, label, required, placeholder, hint }) => (
        <div key={key} className="space-y-1">
          <label className="text-xs text-muted-foreground">{label}{required && ' *'}</label>
          {key === 'color_hex' ? (
            <div className="flex gap-2 items-center">
              <div className="relative h-[34px] w-[34px] shrink-0 cursor-pointer rounded-md border border-border overflow-hidden">
                <span className="absolute inset-0" style={{ backgroundColor: form.color_hex || '#e5e7eb' }} />
                <input
                  type="color"
                  value={/^#[0-9a-fA-F]{6}$/.test(form.color_hex ?? '') ? form.color_hex! : '#e5e7eb'}
                  onChange={e => setForm(prev => ({ ...prev, color_hex: e.target.value }))}
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                />
              </div>
              <input
                className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                value={form.color_hex ?? ''}
                placeholder={placeholder}
                onChange={e => setForm(prev => ({ ...prev, color_hex: e.target.value }))}
              />
            </div>
          ) : (
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              value={(form as any)[key] ?? ''}
              placeholder={placeholder}
              onChange={e => {
                const val = key === 'name' ? e.target.value.toLowerCase().replace(/[^a-z0-9_]+/g, '_') : e.target.value
                setForm(prev => ({ ...prev, [key]: val }))
              }}
              onBlur={key === 'name'
                ? e => setForm(prev => ({ ...prev, name: e.target.value.replace(/^_+|_+$/g, '') }))
                : key === 'display_name'
                ? e => setForm(prev => ({ ...prev, display_name: e.target.value.trim().replace(/\S+/g, w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()) }))
                : undefined}
              required={required}
            />
          )}
          {hint && <p className="text-[11px] text-muted-foreground/70">{hint}</p>}
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
  isMergeMode = false, isMergeSource = false, isGroupDragActive = false,
  showTopInsert = false, showBottomInsert = false,
  selectedTagIds,
  onDeleted, onTagRenamed, onTagDeleted, onGroupUpdated,
  onMergeRequested, onMergeTargetSelected, onTagSelectionToggle,
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

  const { setNodeRef, isOver } = useDroppable({ id: group.id, disabled: isGroupDragActive })
  const { setNodeRef: sortAboveRef, isOver: isOverSortAbove } = useDroppable({
    id: `sort-above:${group.id}`,
    disabled: !isGroupDragActive,
  })
  const { setNodeRef: mergeZoneRef, isOver: isOverMerge } = useDroppable({
    id: `merge:${group.id}`,
    disabled: !isGroupDragActive,
  })
  const { setNodeRef: sortBelowRef, isOver: isOverSortBelow } = useDroppable({
    id: `sort-below:${group.id}`,
    disabled: !isGroupDragActive,
  })

  const {
    attributes: groupDragAttrs,
    listeners: groupDragListeners,
    setNodeRef: setGroupDragRef,
    isDragging: isGroupDragging,
  } = useDraggable({
    id: `group-drag-${group.id}`,
    data: { type: 'group-sort', group: localGroup },
    disabled: !isAdmin || !token,
  })

  function handleGroupSaved(updated: Partial<TagGroupOut>) {
    const next = { ...localGroup, ...updated }
    setLocalGroup(next)
    onGroupUpdated(group.id, { name: updated.name, display_name: updated.display_name, color_hex: updated.color_hex, description: updated.description })
    setEditing(false)
  }

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'relative rounded-xl border border-border bg-card p-5 space-y-3 transition-colors',
        isOver && !isGroupDragging && 'border-primary/50 bg-primary/5',
        isMergeSource && 'ring-2 ring-primary/60',
        isGroupDragging && 'opacity-50',
      )}
    >
      {/* Merge mode overlay (click-based) */}
      {isMergeMode && !isGroupDragActive && (
        <div
          className="absolute inset-0 rounded-xl bg-background/60 backdrop-blur-[2px] flex items-center justify-center z-10 cursor-pointer border-2 border-dashed border-primary/40 hover:border-primary hover:bg-background/30 transition-all"
          onClick={() => onMergeTargetSelected?.(group.id)}
        >
          <div className="text-sm font-medium text-primary flex items-center gap-1.5">
            <GitMerge className="h-4 w-4" />
            Merge here
          </div>
        </div>
      )}

      {/* Top insert indicator */}
      {showTopInsert && (
        <div className="absolute top-0 inset-x-0 h-1 bg-green-400 rounded-t-xl z-20 pointer-events-none" />
      )}
      {/* Bottom insert indicator */}
      {showBottomInsert && (
        <div className="absolute bottom-0 inset-x-0 h-1 bg-green-400 rounded-b-xl z-20 pointer-events-none" />
      )}

      {/* Tripartite drop zones during group drag — sort zones are invisible hit areas */}
      {isGroupDragActive && !isGroupDragging && (
        <div className="absolute inset-0 rounded-xl overflow-hidden z-10 flex flex-col pointer-events-none">
          <div ref={sortAboveRef} className="flex-[3] pointer-events-auto" />
          <div
            ref={mergeZoneRef}
            className={cn(
              'flex-[4] flex items-center justify-center gap-1.5 text-xs font-semibold border-y border-dashed transition-colors pointer-events-auto',
              isOverMerge
                ? 'bg-indigo-500/20 border-indigo-400 text-indigo-600 dark:text-indigo-400'
                : 'bg-transparent border-transparent text-transparent',
            )}
          >
            <GitMerge className="h-3.5 w-3.5" />
            Drop to merge
          </div>
          <div ref={sortBelowRef} className="flex-[3] pointer-events-auto" />
        </div>
      )}

      <div className="flex items-center gap-1">
        {/* Group drag handle */}
        {isAdmin && token && (
          <div
            ref={setGroupDragRef}
            {...groupDragListeners}
            {...groupDragAttrs}
            className="cursor-grab active:cursor-grabbing touch-none shrink-0 text-muted-foreground/40 hover:text-muted-foreground transition-colors"
          >
            <GripVertical className="h-4 w-4" />
          </div>
        )}
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
              variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary"
              onClick={() => onMergeRequested?.(group.id)}
              aria-label="Merge group"
              title="Merge group"
            >
              <GitMerge className="h-3.5 w-3.5" />
            </Button>
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
                  isSelected={selectedTagIds?.has(tag.id) ?? false}
                  onSelectionToggle={() => onTagSelectionToggle?.(tag.id)}
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
              className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {t('tags.collapse')}
            </button>
          )}
        </>
      )}
    </div>
  )
}
