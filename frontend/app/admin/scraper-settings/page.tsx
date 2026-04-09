'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { ChevronDown, Pencil, X, Check, Plus } from 'lucide-react'
import { apiFetch } from '@/lib/api-fetch'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  SourceCard,
  ScraperSetting,
  formatFrequency,
  ActiveBadge,
  ActivityGraph,
  useNextScrapeCountdown,
} from '@/components/scraper-source-card'
import { ArxivKeywordManager } from '@/components/arxiv-keyword-manager'
import { Skeleton } from '@/components/ui/skeleton'
import { useTopic } from '@/contexts/topic-context'

interface ArxivKeyword {
  id: string
  keyword: string
}

interface ArxivCategory {
  id: string
  category: string
}

// ── Accordion shell ──────────────────────────────────────────────────────────

function AccordionSection({
  title,
  badge,
  children,
}: {
  title: string
  badge?: number
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 bg-card hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold capitalize">{title}</span>
          {badge !== undefined && (
            <span className="inline-flex h-5 min-w-5 px-1.5 rounded-full bg-muted text-xs text-muted-foreground items-center justify-center">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="px-4 pb-4 pt-2 space-y-3 bg-muted/20">{children}</div>
      )}
    </div>
  )
}

// ── ArXiv card (singleton, no URL, no delete) ────────────────────────────────

function ArxivSettingCard({
  setting,
  onUpdate,
  onDelete,
  keywords,
  categories,
  onAddKeyword,
  onDeleteKeyword,
  onAddCategory,
  onDeleteCategory,
}: {
  setting: ScraperSetting
  onUpdate: (id: string, data: Partial<ScraperSetting>) => Promise<void>
  onDelete: (id: string) => Promise<void>
  keywords: ArxivKeyword[]
  categories: ArxivCategory[]
  onAddKeyword: (keyword: string) => Promise<void>
  onDeleteKeyword: (id: string) => Promise<void>
  onAddCategory: (category: string) => Promise<void>
  onDeleteCategory: (id: string) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [form, setForm] = useState({
    name: setting.name,
    frequency: setting.frequency,
    is_active: setting.is_active,
  })
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    await onUpdate(setting.id, form)
    setSaving(false)
    setEditing(false)
  }

  const countdown = useNextScrapeCountdown(setting.last_scraped_at, setting.frequency)

  return (
    <>
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      {editing ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">Edit ArXiv Source</span>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">Name</label>
            <input
              className="w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-muted-foreground">
              Frequency (hours)
            </label>
            <input
              type="number"
              min={1}
              className="w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={form.frequency}
              onChange={e => setForm(f => ({ ...f, frequency: Number(e.target.value) }))}
            />
            {form.frequency >= 24 && (
              <p className="text-xs text-muted-foreground mt-1">
                {formatFrequency(form.frequency)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={form.is_active}
              onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))}
            />
            <span className="text-sm text-muted-foreground">Active</span>
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
      ) : (
        <div className="flex flex-col gap-3">
          {/* Top row: name + badge/actions */}
          <div className="flex items-start justify-between gap-3">
            <p className="font-bold text-lg leading-snug">{setting.name}</p>
            <div className="flex items-center gap-1 shrink-0">
              <ActiveBadge
                active={setting.is_active}
                onToggle={() => onUpdate(setting.id, { is_active: !setting.is_active })}
              />
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(true)}>
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

          {/* Middle + bottom: countdown, frequency, activity (right-aligned) */}
          <div className="flex justify-end">
            <div className="flex flex-col items-end gap-2">
              <div className="text-right leading-tight space-y-0.5">
                <p className="text-xs font-medium text-orange-500 tabular-nums">
                  next scrape in {countdown}
                </p>
                <p className="text-xs text-muted-foreground">{formatFrequency(setting.frequency)}</p>
              </div>
              <ActivityGraph activity={setting.activity} />
            </div>
          </div>
        </div>
      )}

      <div className="border-t border-border pt-4">
        <ArxivKeywordManager
          keywords={keywords}
          categories={categories}
          onAddKeyword={onAddKeyword}
          onDeleteKeyword={onDeleteKeyword}
          onAddCategory={onAddCategory}
          onDeleteCategory={onDeleteCategory}
        />
      </div>
    </div>

    <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete arXiv source?</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Are you sure you want to delete <strong>{setting.name}</strong>? This cannot be undone.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="destructive" onClick={() => { setConfirmDelete(false); onDelete(setting.id) }}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  )
}

// ── Add source card (RSS / Blog) ─────────────────────────────────────────────

function AddSourceCard({
  sourceType,
  onAdd,
}: {
  sourceType: 'rss' | 'blog'
  onAdd: (data: Omit<ScraperSetting, 'id'>) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const emptyForm = {
    name: '',
    url: '',
    frequency: 24,
    is_active: true,
    selector_config: { article_link: '', title: '', content: '' },
  }
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [topicId, setTopicId] = useState<string>('')
  const { topics } = useTopic()

  async function handleAdd() {
    if (!form.name || !form.url) return
    setSaving(true)
    const payload: any = {
      source_type: sourceType,
      name: form.name,
      url: form.url,
      frequency: form.frequency,
      is_active: form.is_active,
      topic_id: topicId || undefined,
    }
    if (sourceType === 'blog') payload.selector_config = form.selector_config
    await onAdd(payload)
    setSaving(false)
    setExpanded(false)
    setForm(emptyForm)
    setTopicId('')
  }

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full rounded-xl border border-dashed border-border bg-card/50 py-4 flex items-center justify-center gap-2 text-sm text-muted-foreground hover:border-foreground/30 hover:text-foreground transition-colors"
      >
        <Plus className="h-4 w-4" />
        Add source
      </button>
    )
  }

  const inputClass =
    'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
  const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">New {sourceType.toUpperCase()} Source</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setExpanded(false)}>
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
            placeholder="e.g. Hacker News"
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

        {sourceType === 'blog' && (
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
                    key === 'article_link'
                      ? 'a.post-link'
                      : key === 'title'
                      ? 'h1.post-title'
                      : '.post-content'
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

        <div className="space-y-1.5">
          <label className={labelClass}>Topic</label>
          <select
            value={topicId}
            onChange={e => setTopicId(e.target.value)}
            className="w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            required
          >
            <option value="">Select a topic...</option>
            {topics.map(t => (
              <option key={t.id} value={t.id}>{t.display_name}</option>
            ))}
          </select>
        </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={handleAdd} disabled={saving || !form.name || !form.url}>
          <Check className="h-4 w-4 mr-1" />
          Add
        </Button>
        <Button size="sm" variant="outline" onClick={() => setExpanded(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

// ── Skeleton card ─────────────────────────────────────────────────────────────

function ScraperSourceCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <Skeleton className="h-5 w-2/5" />
        <div className="flex gap-1">
          <Skeleton className="h-6 w-14 rounded-full" />
          <Skeleton className="h-8 w-8 rounded-md" />
          <Skeleton className="h-8 w-8 rounded-md" />
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <Skeleton className="h-3 w-28" />
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ScraperSettingsPage() {
  const { data: session, status } = useSession()
  const [settings, setSettings] = useState<ScraperSetting[]>([])
  const [keywords, setKeywords] = useState<ArxivKeyword[]>([])
  const [categories, setCategories] = useState<ArxivCategory[]>([])
  const [isLoading, setIsLoading] = useState(true)

  if (status === 'unauthenticated') redirect('/login')
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    const headers = { Authorization: `Bearer ${token}` }
    setIsLoading(true)
    Promise.all([
      apiFetch('/scraper-settings', { headers }).then(r => r.json()),
      apiFetch('/arxiv-keywords', { headers }).then(r => r.json()),
      apiFetch('/arxiv-categories', { headers }).then(r => r.json()),
    ]).then(([s, k, c]) => {
      setSettings(Array.isArray(s) ? s : [])
      setKeywords(Array.isArray(k) ? k : [])
      setCategories(Array.isArray(c) ? c : [])
    }).finally(() => setIsLoading(false))
  }, [token])

  const byType = (type: ScraperSetting['source_type']) =>
    settings.filter(s => s.source_type === type)

  async function handleUpdate(id: string, data: Partial<ScraperSetting>) {
    // Optimistic update
    setSettings(prev => prev.map(s => (s.id === id ? { ...s, ...data } : s)))
    await apiFetch(`/scraper-settings/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    })
  }

  async function handleDelete(id: string) {
    setSettings(prev => prev.filter(s => s.id !== id))
    await apiFetch(`/scraper-settings/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
  }

  async function handleCreate(data: Omit<ScraperSetting, 'id'>) {
    const res = await apiFetch('/scraper-settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    })
    if (res.ok) {
      const created = await res.json()
      setSettings(prev => [...prev, created])
    }
  }

  async function handleAddKeyword(keyword: string) {
    const res = await apiFetch('/arxiv-keywords', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ keyword }),
    })
    if (res.ok) {
      const created = await res.json()
      setKeywords(prev => [...prev, created])
    }
  }

  async function handleDeleteKeyword(id: string) {
    setKeywords(prev => prev.filter(k => k.id !== id))
    await apiFetch(`/arxiv-keywords/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
  }

  async function handleAddCategory(category: string) {
    const res = await apiFetch('/arxiv-categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ category }),
    })
    if (res.ok) {
      const created = await res.json()
      setCategories(prev => [...prev, created])
    }
  }

  async function handleDeleteCategory(id: string) {
    setCategories(prev => prev.filter(c => c.id !== id))
    await apiFetch(`/arxiv-categories/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
  }

  const arxivSettings = byType('arxiv')
  const blogSettings = byType('blog')
  const rssSettings = byType('rss')

  return (
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">Scraper Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your news sources and scraping schedule.
        </p>
      </div>

      <div className="space-y-4">
        {isLoading ? (
          <>
            {[0, 1, 2].map(i => (
              <div key={i} className="rounded-xl border border-border overflow-hidden">
                <div className="px-5 py-4 bg-card flex items-center justify-between">
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-4 w-4" />
                </div>
                <div className="px-4 pb-4 pt-2 space-y-3 bg-muted/20">
                  <ScraperSourceCardSkeleton />
                </div>
              </div>
            ))}
          </>
        ) : (
          <>
            <AccordionSection title="arXiv" badge={arxivSettings.length}>
              {arxivSettings.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No arXiv source found.</p>
              ) : (
                arxivSettings.map(s => (
                  <ArxivSettingCard
                    key={s.id}
                    setting={s}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    keywords={keywords}
                    categories={categories}
                    onAddKeyword={handleAddKeyword}
                    onDeleteKeyword={handleDeleteKeyword}
                    onAddCategory={handleAddCategory}
                    onDeleteCategory={handleDeleteCategory}
                  />
                ))
              )}
            </AccordionSection>

            <AccordionSection title="Blog" badge={blogSettings.length}>
              {blogSettings.map(s => (
                <SourceCard key={s.id} setting={s} onUpdate={handleUpdate} onDelete={handleDelete} />
              ))}
              <AddSourceCard sourceType="blog" onAdd={handleCreate} />
            </AccordionSection>

            <AccordionSection title="RSS" badge={rssSettings.length}>
              {rssSettings.map(s => (
                <SourceCard key={s.id} setting={s} onUpdate={handleUpdate} onDelete={handleDelete} />
              ))}
              <AddSourceCard sourceType="rss" onAdd={handleCreate} />
            </AccordionSection>
          </>
        )}
      </div>
    </div>
  )
}
