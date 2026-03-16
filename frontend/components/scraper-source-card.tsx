'use client'
import { useState } from 'react'
import { Pencil, X, Check } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'

export interface ScraperSetting {
  id: string
  source_type: 'rss' | 'blog' | 'arxiv'
  name: string
  url: string
  frequency: number
  is_active: boolean
  selector_config?: { article_link: string; title: string; content: string } | null
}

export function formatFrequency(hours: number): string {
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  const rem = hours % 24
  return rem > 0 ? `${hours}h (= ${days}d ${rem}h)` : `${hours}h (= ${days}d)`
}

const inputClass =
  'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

export function SourceCard({
  setting,
  onUpdate,
  onDelete,
}: {
  setting: ScraperSetting
  onUpdate: (id: string, data: Partial<ScraperSetting>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [form, setForm] = useState({
    name: setting.name,
    url: setting.url,
    frequency: setting.frequency,
    is_active: setting.is_active,
    selector_config: setting.selector_config ?? { article_link: '', title: '', content: '' },
  })
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    const payload: Partial<ScraperSetting> = {
      name: form.name,
      url: form.url,
      frequency: form.frequency,
      is_active: form.is_active,
    }
    if (setting.source_type === 'blog') {
      payload.selector_config = form.selector_config
    }
    await onUpdate(setting.id, payload)
    setSaving(false)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Edit Source</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-3">
          <div>
            <label className={labelClass}>Name</label>
            <input
              className={inputClass}
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelClass}>URL</label>
            <input
              className={inputClass}
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              placeholder="https://..."
            />
          </div>
          <div>
            <label className={labelClass}>Frequency (hours)</label>
            <input
              type="number"
              min={1}
              className={inputClass}
              value={form.frequency}
              onChange={e => setForm(f => ({ ...f, frequency: Number(e.target.value) }))}
            />
            {form.frequency >= 24 && (
              <p className="text-xs text-muted-foreground mt-1">{formatFrequency(form.frequency)}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={form.is_active}
              onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))}
            />
            <span className="text-sm text-muted-foreground">Active</span>
          </div>

          {setting.source_type === 'blog' && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                CSS Selectors
              </p>
              {(['article_link', 'title', 'content'] as const).map(key => (
                <div key={key}>
                  <label className={labelClass}>{key.replace('_', ' ')}</label>
                  <input
                    className={inputClass}
                    value={form.selector_config[key]}
                    placeholder={
                      key === 'article_link' ? 'a.post-link' : key === 'title' ? 'h1.post-title' : '.post-content'
                    }
                    onChange={e =>
                      setForm(f => ({
                        ...f,
                        selector_config: { ...f.selector_config, [key]: e.target.value },
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            <Check className="h-4 w-4 mr-1" />
            Save
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <p className="font-semibold text-sm">{setting.name}</p>
            <p className="text-xs text-muted-foreground truncate max-w-xs">{setting.url}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className="inline-flex items-center h-5 px-2 rounded-full border border-border text-xs text-muted-foreground">
                {formatFrequency(setting.frequency)}
              </span>
              <Switch
                checked={setting.is_active}
                onCheckedChange={v => onUpdate(setting.id, { is_active: v })}
              />
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setEditing(true)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
              onClick={() => setConfirmDelete(true)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete source?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <strong>{setting.name}</strong>? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmDelete(false)
                onDelete(setting.id)
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
