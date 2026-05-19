'use client'
import { useState } from 'react'
import { Pencil, X, Check, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { TagGroupOut, TagOut } from '@/lib/api/tags'
import { renameTag, deleteTag, deleteTagGroup } from '@/lib/api/tags'

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
  groupId,
  onRenamed,
  onDeleted,
}: {
  tag: TagOut
  isAdmin: boolean
  token?: string
  groupId: string
  onRenamed: (tagId: string, name: string) => void
  onDeleted: (tagId: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(tag.name)

  async function handleRename() {
    if (!token || !value.trim()) return
    await renameTag(tag.id, value.trim(), token)
    onRenamed(tag.id, value.trim())
    setEditing(false)
  }

  async function handleDelete() {
    if (!token) return
    await deleteTag(tag.id, token)
    onDeleted(tag.id)
  }

  if (editing) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-background text-xs">
        <input
          className="w-24 bg-transparent text-xs focus:outline-none"
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleRename()}
          autoFocus
        />
        <button onClick={handleRename}><Check className="h-3 w-3 text-green-600" /></button>
        <button onClick={() => { setValue(tag.name); setEditing(false) }}><X className="h-3 w-3" /></button>
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-border bg-muted/50 text-xs">
      {tag.name}
      <span className="text-muted-foreground">({tag.article_count})</span>
      {isAdmin && (
        <>
          <button onClick={() => setEditing(true)} className="hover:text-foreground text-muted-foreground">
            <Pencil className="h-2.5 w-2.5" />
          </button>
          <button onClick={handleDelete} className="hover:text-destructive text-muted-foreground">
            <X className="h-2.5 w-2.5" />
          </button>
        </>
      )}
    </span>
  )
}

export function TagGroupCard({ group, isAdmin, token, onDeleted, onTagRenamed, onTagDeleted }: Props) {
  const [tags, setTags] = useState<TagOut[]>(group.tags)

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {group.color_hex && (
            <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: group.color_hex }} />
          )}
          <span className="font-semibold text-sm">{group.display_name}</span>
          <span className="text-xs text-muted-foreground">({tags.length} tags)</span>
        </div>
        {isAdmin && token && (
          <Button
            variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive"
            onClick={async () => { await deleteTagGroup(group.id, token); onDeleted(group.id) }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {tags.map(tag => (
          <TagBadge
            key={tag.id}
            tag={tag}
            isAdmin={isAdmin}
            token={token}
            groupId={group.id}
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
          <span className="text-xs text-muted-foreground italic">No tags yet</span>
        )}
      </div>
    </div>
  )
}
