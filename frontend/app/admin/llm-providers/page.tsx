'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { redirect } from 'next/navigation'
import { Pencil, X, Check, Plus } from 'lucide-react'
import { apiFetch } from '@/lib/api-fetch'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'

interface LlmProvider {
  id: string
  name: string
  model: string
  api_key_env: string
  priority: number
  is_active: boolean
  rpm: number | null
  tpm: number | null
  rpd: number | null
  usage_24h: number
  created_at: string | null
  updated_at: string | null
}

const PROVIDER_NAMES = ['gemini', 'claude', 'openrouter'] as const

// ── Provider Card ─────────────────────────────────────────────────────────────

function ProviderCard({
  provider,
  onUpdate,
  onDelete,
}: {
  provider: LlmProvider
  onUpdate: (id: string, data: Partial<LlmProvider>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: provider.name,
    model: provider.model,
    api_key_env: provider.api_key_env,
    priority: provider.priority,
    is_active: provider.is_active,
    rpm: provider.rpm ?? '',
    tpm: provider.tpm ?? '',
    rpd: provider.rpd ?? '',
  })

  const inputClass =
    'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
  const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

  async function handleSave() {
    setSaving(true)
    await onUpdate(provider.id, {
      name: form.name,
      model: form.model,
      api_key_env: form.api_key_env,
      priority: Number(form.priority),
      is_active: form.is_active,
      rpm: form.rpm !== '' ? Number(form.rpm) : null,
      tpm: form.tpm !== '' ? Number(form.tpm) : null,
      rpd: form.rpd !== '' ? Number(form.rpd) : null,
    })
    setSaving(false)
    setEditing(false)
  }

  return (
    <>
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        {editing ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">Edit Provider</span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>Provider</label>
                <select
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className={inputClass}
                >
                  {PROVIDER_NAMES.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className={labelClass}>Priority</label>
                <input
                  type="number"
                  min={1}
                  className={inputClass}
                  value={form.priority}
                  onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))}
                />
              </div>
            </div>
            <div>
              <label className={labelClass}>Model</label>
              <input
                className={inputClass}
                value={form.model}
                onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                placeholder="e.g. gemini-2.5-flash"
              />
            </div>
            <div>
              <label className={labelClass}>API Key Env Var</label>
              <input
                className={inputClass}
                value={form.api_key_env}
                onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
                placeholder="e.g. GEMINI_API_KEY"
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              {(['rpm', 'tpm', 'rpd'] as const).map(field => (
                <div key={field}>
                  <label className={labelClass}>{field.toUpperCase()}</label>
                  <input
                    type="number"
                    min={0}
                    className={inputClass}
                    value={form[field]}
                    placeholder="—"
                    onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
                  />
                </div>
              ))}
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
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <p className="font-bold leading-snug">{provider.model}</p>
              <p className="text-xs text-muted-foreground capitalize">{provider.name}</p>
              <p className="text-xs text-muted-foreground font-mono">{provider.api_key_env}</p>
              {(provider.rpm || provider.tpm || provider.rpd) && (
                <p className="text-xs text-muted-foreground">
                  {[
                    provider.rpm && `${provider.rpm} rpm`,
                    provider.tpm && `${provider.tpm} tpm`,
                    provider.rpd && `${provider.rpd} rpd`,
                  ].filter(Boolean).join(' · ')}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                {provider.usage_24h} calls in last 24h
              </p>
            </div>
            <div className="flex flex-col items-end gap-2 shrink-0">
              <div className="flex items-center gap-1">
                <span className="text-xs text-muted-foreground mr-1">p{provider.priority}</span>
                <Switch
                  checked={provider.is_active}
                  onCheckedChange={v => onUpdate(provider.id, { is_active: v })}
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
          </div>
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete provider?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Delete <strong>{provider.model}</strong>? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button variant="destructive" onClick={() => { setConfirmDelete(false); onDelete(provider.id) }}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ── Add Provider Card ─────────────────────────────────────────────────────────

function AddProviderCard({ onAdd }: { onAdd: (data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>) => Promise<void> }) {
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const emptyForm = {
    name: 'gemini' as string,
    model: '',
    api_key_env: '',
    priority: 1,
    is_active: true,
    rpm: '' as number | string,
    tpm: '' as number | string,
    rpd: '' as number | string,
  }
  const [form, setForm] = useState(emptyForm)

  const inputClass =
    'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
  const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

  async function handleAdd() {
    if (!form.model || !form.api_key_env) return
    setSaving(true)
    await onAdd({
      name: form.name,
      model: form.model,
      api_key_env: form.api_key_env,
      priority: Number(form.priority),
      is_active: form.is_active,
      rpm: form.rpm !== '' ? Number(form.rpm) : null,
      tpm: form.tpm !== '' ? Number(form.tpm) : null,
      rpd: form.rpd !== '' ? Number(form.rpd) : null,
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
        <Plus className="h-4 w-4" />
        Add provider
      </button>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">New Provider</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setExpanded(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Provider</label>
          <select
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            className={inputClass}
          >
            {PROVIDER_NAMES.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className={labelClass}>Priority</label>
          <input
            type="number"
            min={1}
            className={inputClass}
            value={form.priority}
            onChange={e => setForm(f => ({ ...f, priority: Number(e.target.value) }))}
          />
        </div>
      </div>
      <div>
        <label className={labelClass}>Model</label>
        <input
          className={inputClass}
          value={form.model}
          onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
          placeholder="e.g. gemini-2.5-flash"
        />
      </div>
      <div>
        <label className={labelClass}>API Key Env Var</label>
        <input
          className={inputClass}
          value={form.api_key_env}
          onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
          placeholder="e.g. GEMINI_API_KEY"
        />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {(['rpm', 'tpm', 'rpd'] as const).map(field => (
          <div key={field}>
            <label className={labelClass}>{field.toUpperCase()}</label>
            <input
              type="number"
              min={0}
              className={inputClass}
              value={form[field]}
              placeholder="—"
              onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
            />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Switch
          checked={form.is_active}
          onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))}
        />
        <span className="text-sm text-muted-foreground">Active</span>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={handleAdd} disabled={saving || !form.model || !form.api_key_env}>
          <Check className="h-4 w-4 mr-1" />
          Add
        </Button>
        <Button size="sm" variant="outline" onClick={() => setExpanded(false)}>Cancel</Button>
      </div>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function ProviderCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-8 w-20 rounded-full" />
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function LlmProvidersPage() {
  const { data: session, status } = useSession()
  const [providers, setProviders] = useState<LlmProvider[]>([])
  const [isLoading, setIsLoading] = useState(true)

  if (status === 'unauthenticated') redirect('/login')
  if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') redirect('/settings')

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    apiFetch('/llm-providers', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => setProviders(Array.isArray(data) ? data : []))
      .finally(() => setIsLoading(false))
  }, [token])

  async function handleUpdate(id: string, data: Partial<LlmProvider>) {
    setProviders(prev => prev.map(p => (p.id === id ? { ...p, ...data } : p)))
    await apiFetch(`/llm-providers/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    })
  }

  async function handleDelete(id: string) {
    setProviders(prev => prev.filter(p => p.id !== id))
    await apiFetch(`/llm-providers/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
  }

  async function handleCreate(data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>) {
    const res = await apiFetch('/llm-providers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    })
    if (res.ok) {
      const created = await res.json()
      setProviders(prev => [...prev, created])
    }
  }

  return (
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">LLM Providers</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage LLM providers and their rate limits. Lower priority number = tried first.
        </p>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          [0, 1, 2].map(i => <ProviderCardSkeleton key={i} />)
        ) : (
          <>
            {providers.map(p => (
              <ProviderCard
                key={p.id}
                provider={p}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
              />
            ))}
            <AddProviderCard onAdd={handleCreate} />
          </>
        )}
      </div>
    </div>
  )
}