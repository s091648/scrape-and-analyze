'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { Pencil, X, Check, Plus, RotateCcw } from 'lucide-react'
import { fetchTopics, updateTopic, deleteTopic, createTopic, type Topic } from '@/lib/api/topics'
import { useTopic } from '@/lib/providers'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'
import { TagModeSelector, type TagMode } from '@/components/features/tags/tag-mode-selector'


const inputClass =
  'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'
const textareaClass =
  'w-full px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none'

// ── Topic row ────────────────────────────────────────────────────────────────

function TopicRow({
  topic,
  onUpdate,
  onDelete,
}: {
  topic: Topic
  onUpdate: (id: string, data: Partial<Topic>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [form, setForm] = useState({
    display_name: topic.display_name,
    description: topic.description ?? '',
    color_hex: topic.color_hex ?? '',
    prompt_override: topic.prompt_override ?? '',
    sort_order: topic.sort_order ?? 0,
    is_active: topic.is_active,
    tag_mode: (topic.tag_mode ?? 'unsupervised') as TagMode,
  })
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    await onUpdate(topic.id, {
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order,
      is_active: form.is_active,
      tag_mode: form.tag_mode,
    })
    setSaving(false)
    setEditing(false)
  }

  return (
    <>
      <div className={`rounded-xl border border-border bg-card p-5 space-y-3 ${!topic.is_active ? 'opacity-60' : ''}`}>
        {editing ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">{t('admin.editTopic')}</span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>{t('admin.displayName')}</label>
                <input
                  className={inputClass}
                  value={form.display_name}
                  onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                />
              </div>
              <div>
                <label className={labelClass}>{t('admin.colorHex')}</label>
                <div className="flex gap-2 items-center">
                  <div className="relative h-9 w-9 shrink-0 cursor-pointer rounded-lg border border-border overflow-hidden">
                    <span className="absolute inset-0" style={{ backgroundColor: form.color_hex || '#e5e7eb' }} />
                    <input
                      type="color"
                      value={/^#[0-9a-fA-F]{6}$/.test(form.color_hex) ? form.color_hex : '#e5e7eb'}
                      onChange={e => setForm(f => ({ ...f, color_hex: e.target.value }))}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                    />
                  </div>
                  <input
                    className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    value={form.color_hex}
                    placeholder="#3b82f6"
                    onChange={e => setForm(f => ({ ...f, color_hex: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            <div>
              <label className={labelClass}>{t('admin.description')}</label>
              <textarea
                className={textareaClass}
                rows={2}
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              />
            </div>

            <div>
              <label className={labelClass}>{t('admin.promptOverride')}</label>
              <textarea
                className={textareaClass}
                rows={3}
                placeholder={t('admin.promptOverridePlaceholder')}
                value={form.prompt_override}
                onChange={e => setForm(f => ({ ...f, prompt_override: e.target.value }))}
              />
            </div>

            <div className="grid grid-cols-2 gap-3 items-end">
              <div>
                <label className={labelClass}>{t('admin.sortOrder')}</label>
                <input
                  type="number"
                  className={inputClass}
                  value={form.sort_order}
                  onChange={e => setForm(f => ({ ...f, sort_order: Number(e.target.value) }))}
                />
              </div>
              <div className="flex items-center gap-2 pb-0.5">
                <Switch
                  checked={form.is_active}
                  onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))}
                />
                <span className="text-sm text-muted-foreground">{t('admin.active')}</span>
              </div>
            </div>

            <div>
              <label className={labelClass}>{t('tags.tagMode')}</label>
              <TagModeSelector
                value={form.tag_mode}
                onChange={v => setForm(f => ({ ...f, tag_mode: v }))}
              />
            </div>

            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving || !form.display_name}>
                <Check className="h-4 w-4 mr-1" /> {t('admin.save')}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>{t('admin.cancel')}</Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-3 min-w-0">
              {topic.color_hex && (
                <span
                  className="mt-1 h-3.5 w-3.5 rounded-full shrink-0 border border-border"
                  style={{ backgroundColor: topic.color_hex }}
                />
              )}
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-semibold text-sm leading-snug">{topic.display_name}</p>
                  {!topic.is_active && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium uppercase tracking-wide">
                      {t('admin.inactive')}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">{topic.name}</p>
                {topic.description && (
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{topic.description}</p>
                )}
                {topic.sort_order !== null && (
                  <p className="text-xs text-muted-foreground mt-1">{t('admin.order')}: {topic.sort_order}</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(true)}>
                <Pencil className="h-4 w-4" />
              </Button>
              {topic.is_active ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-muted-foreground"
                  title="Restore topic"
                  onClick={() => onUpdate(topic.id, { is_active: true })}
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t('admin.deactivateTopic')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <strong>{topic.display_name}</strong> {t('admin.deactivateTopicDesc')}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>{t('admin.cancel')}</Button>
            <Button variant="destructive" onClick={() => { setConfirmDelete(false); onDelete(topic.id) }}>
              {t('admin.deactivate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ── Add topic form ────────────────────────────────────────────────────────────

function AddTopicCard({ onAdd }: { onAdd: (data: Omit<Topic, 'id' | 'is_active'>) => Promise<void> }) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const emptyForm = {
    name: '',
    display_name: '',
    description: '',
    color_hex: '',
    prompt_override: '',
    sort_order: 0,
    tag_mode: 'unsupervised' as TagMode,
  }
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)

  async function handleAdd() {
    if (!form.name || !form.display_name) return
    setSaving(true)
    await onAdd({
      name: form.name,
      display_name: form.display_name,
      description: form.description || null,
      color_hex: form.color_hex || null,
      prompt_override: form.prompt_override || null,
      sort_order: form.sort_order || null,
      tag_mode: form.tag_mode,
    })
    setSaving(false)
    setExpanded(false)
    setForm(emptyForm)
  }

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full rounded-xl border border-dashed border-border bg-card/50 py-4 flex items-center justify-center gap-2 text-sm text-muted-foreground hover:border-foreground/30 hover:text-foreground transition-colors"
      >
        <Plus className="h-4 w-4" /> {t('admin.addTopic')}
      </button>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{t('admin.newTopic')}</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setExpanded(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>{t('admin.slug')} <span className="text-destructive">*</span></label>
          <input
            className={inputClass}
            value={form.name}
            placeholder="digital-twin"
            onChange={e => setForm(f => ({ ...f, name: e.target.value.toLowerCase().replace(/\s+/g, '-') }))}
          />
          <p className="text-[10px] text-muted-foreground mt-1">{t('admin.immutableAfterCreation')}</p>
        </div>
        <div>
          <label className={labelClass}>{t('admin.displayName')} <span className="text-destructive">*</span></label>
          <input
            className={inputClass}
            value={form.display_name}
            placeholder="Digital Twin"
            onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>{t('admin.colorHex')}</label>
          <div className="flex gap-2 items-center">
            <div className="relative h-9 w-9 shrink-0 cursor-pointer rounded-lg border border-border overflow-hidden">
              <span className="absolute inset-0" style={{ backgroundColor: form.color_hex || '#e5e7eb' }} />
              <input
                type="color"
                value={/^#[0-9a-fA-F]{6}$/.test(form.color_hex) ? form.color_hex : '#e5e7eb'}
                onChange={e => setForm(f => ({ ...f, color_hex: e.target.value }))}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
            </div>
            <input
              className="flex-1 h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={form.color_hex}
              placeholder="#3b82f6"
              onChange={e => setForm(f => ({ ...f, color_hex: e.target.value }))}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>{t('admin.sortOrder')}</label>
          <input
            type="number"
            className={inputClass}
            value={form.sort_order}
            onChange={e => setForm(f => ({ ...f, sort_order: Number(e.target.value) }))}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>{t('admin.description')}</label>
        <textarea
          className={textareaClass}
          rows={2}
          value={form.description}
          onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
        />
      </div>

      <div>
        <label className={labelClass}>{t('admin.promptOverride')}</label>
        <textarea
          className={textareaClass}
          rows={3}
          placeholder={t('admin.promptOverridePlaceholder')}
          value={form.prompt_override}
          onChange={e => setForm(f => ({ ...f, prompt_override: e.target.value }))}
        />
      </div>

      <div>
        <label className={labelClass}>{t('tags.tagMode')}</label>
        <TagModeSelector
          value={form.tag_mode}
          onChange={v => setForm(f => ({ ...f, tag_mode: v }))}
        />
      </div>

      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={handleAdd}
          disabled={saving || !form.name || !form.display_name}
        >
          <Check className="h-4 w-4 mr-1" /> {t('admin.create')}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setExpanded(false)}>{t('admin.cancel')}</Button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TopicsPage() {
  const { data: session, status } = useSession()
  const { t } = useI18n()
  const [topics, setTopics] = useState<Topic[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showInactive, setShowInactive] = useState(false)
  const { refresh: refreshTopicContext } = useTopic()

  if (status === 'unauthenticated') redirect('/login')
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    fetchTopics({ include_inactive: true }, token)
      .then(setTopics)
      .finally(() => setIsLoading(false))
  }, [token])

  async function handleUpdate(id: string, data: Partial<Topic>) {
    setTopics(prev => prev.map(t => (t.id === id ? { ...t, ...data } : t)))
    await updateTopic(id, data, token)
    await refreshTopicContext()
  }

  async function handleDelete(id: string) {
    setTopics(prev => prev.map(t => (t.id === id ? { ...t, is_active: false } : t)))
    await deleteTopic(id, token)
    await refreshTopicContext()
  }

  async function handleCreate(data: Omit<Topic, 'id' | 'is_active'>) {
    const created = await createTopic(data, token)
    setTopics(prev => [...prev, created])
    await refreshTopicContext()
  }

  const visible = showInactive ? topics : topics.filter(t => t.is_active)

  return (
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.topics')}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('admin.manageTopicsDesc')}
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {topics.filter(t => t.is_active).length} {t('admin.active')}
            {topics.some(t => !t.is_active) && `, ${topics.filter(t => !t.is_active).length} ${t('admin.inactive')}`}
          </p>
          {topics.some(t => !t.is_active) && (
            <button
              onClick={() => setShowInactive(v => !v)}
              className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
            >
              {showInactive ? t('admin.hideInactive') : t('admin.showInactive')}
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[0, 1, 2].map(i => (
              <div key={i} className="rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between">
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <div className="flex gap-1">
                    <Skeleton className="h-8 w-8 rounded-md" />
                    <Skeleton className="h-8 w-8 rounded-md" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {visible.map(topicItem => (
              <TopicRow key={topicItem.id} topic={topicItem} onUpdate={handleUpdate} onDelete={handleDelete} />
            ))}
            <AddTopicCard onAdd={handleCreate} />
          </div>
        )}
      </div>
    </div>
  )
}
