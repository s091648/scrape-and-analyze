'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { Pencil, X, Check, Plus } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AccordionSection } from '@/components/ui/accordion-section'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  type RagEmbeddingProvider,
  fetchRagEmbeddingProviders,
  createRagEmbeddingProvider,
  updateRagEmbeddingProvider,
  deleteRagEmbeddingProvider,
} from '@/lib/api'
import { useI18n } from '@/lib/providers'

const inputClass =
  'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

function ProviderCard({
  provider,
  onUpdate,
  onDelete,
}: {
  provider: RagEmbeddingProvider
  onUpdate: (id: string, data: Partial<RagEmbeddingProvider>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    provider_type: provider.provider_type,
    model: provider.model ?? '',
    endpoint_url: provider.endpoint_url ?? '',
    api_key_env: provider.api_key_env ?? '',
    dimension: provider.dimension,
    is_active: provider.is_active,
    rpm: provider.rpm ?? ('' as number | string),
    tpm: provider.tpm ?? ('' as number | string),
    rpd: provider.rpd ?? ('' as number | string),
  })

  async function handleSave() {
    setSaving(true)
    await onUpdate(provider.id, {
      provider_type: form.provider_type,
      model: form.model || null,
      endpoint_url: form.endpoint_url || null,
      api_key_env: form.api_key_env || null,
      dimension: Number(form.dimension),
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
              <span className="text-sm font-semibold">{t('admin.editProvider')}</span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div>
              <label className={labelClass}>{t('admin.providerMode')}</label>
              <select
                value={form.provider_type}
                onChange={e => setForm(f => ({ ...f, provider_type: e.target.value as 'endpoint' | 'local' }))}
                className={inputClass}
              >
                <option value="endpoint">{t('admin.mode_endpoint')}</option>
                <option value="local">{t('admin.mode_local')}</option>
              </select>
            </div>
            {form.provider_type === 'endpoint' ? (
              <>
                <div>
                  <label className={labelClass}>{t('admin.endpointUrl')}</label>
                  <input
                    className={inputClass}
                    value={form.endpoint_url}
                    onChange={e => setForm(f => ({ ...f, endpoint_url: e.target.value }))}
                    placeholder={t('admin.endpointUrlPlaceholder')}
                  />
                </div>
                <div>
                  <label className={labelClass}>{t('admin.apiKeyEnvVar')} ({t('admin.optional')})</label>
                  <input
                    className={inputClass}
                    value={form.api_key_env}
                    onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
                    placeholder={t('admin.apiKeyEnvVarPlaceholder')}
                  />
                </div>
              </>
            ) : (
              <div>
                <label className={labelClass}>{t('admin.fastembedModel')}</label>
                <input
                  className={inputClass}
                  value={form.model}
                  onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                  placeholder={t('admin.fastembedModelPlaceholder')}
                />
              </div>
            )}
            <div>
              <label className={labelClass}>{t('admin.dimension')}</label>
              <input
                type="number"
                min={1}
                className={inputClass}
                value={form.dimension}
                onChange={e => setForm(f => ({ ...f, dimension: Number(e.target.value) }))}
              />
            </div>
            <div className="grid grid-cols-3 gap-3">
              {(['rpm', 'tpm', 'rpd'] as const).map(field => (
                <div key={field}>
                  <label className={labelClass}>{t(`admin.${field}`)}</label>
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
              <span className="text-sm text-muted-foreground">{t('admin.active')}</span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <Check className="h-4 w-4 mr-1" />
                {t('admin.save')}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
                {t('admin.cancel')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 space-y-1">
              <p className="font-bold leading-snug">
                {provider.provider_type === 'endpoint' ? provider.endpoint_url : provider.model}
              </p>
              <p className="text-xs text-muted-foreground capitalize">{t(`admin.mode_${provider.provider_type}`)}</p>
              {provider.api_key_env && (
                <p className="text-xs text-muted-foreground font-mono">{provider.api_key_env}</p>
              )}
              <p className="text-xs text-muted-foreground">{t('admin.dimension')}: {provider.dimension}</p>
              {(provider.rpm || provider.tpm || provider.rpd) && (
                <p className="text-xs text-muted-foreground">
                  {[
                    provider.rpm && `${provider.rpm} rpm`,
                    provider.tpm && `${provider.tpm} tpm`,
                    provider.rpd && `${provider.rpd} rpd`,
                  ].filter(Boolean).join(' · ')}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0">
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
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t('admin.deleteProvider')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('admin.deleteProviderConfirm', {
              model: provider.endpoint_url ?? provider.model ?? provider.role,
            })}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              {t('admin.cancel')}
            </Button>
            <Button variant="destructive" onClick={() => { setConfirmDelete(false); onDelete(provider.id) }}>
              {t('admin.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function AddProviderCard({
  role,
  onAdd,
}: {
  role: 'dense' | 'sparse'
  onAdd: (data: Omit<RagEmbeddingProvider, 'id' | 'created_at' | 'updated_at'>) => Promise<void>
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const emptyForm = {
    provider_type: 'endpoint' as 'endpoint' | 'local',
    model: '',
    endpoint_url: '',
    api_key_env: '',
    dimension: role === 'sparse' ? 30522 : 768,
    is_active: true,
    rpm: '' as number | string,
    tpm: '' as number | string,
    rpd: '' as number | string,
  }
  const [form, setForm] = useState(emptyForm)

  async function handleAdd() {
    if (form.provider_type === 'endpoint' && !form.endpoint_url) return
    if (form.provider_type === 'local' && !form.model) return
    setSaving(true)
    await onAdd({
      role,
      provider_type: form.provider_type,
      model: form.model || null,
      endpoint_url: form.endpoint_url || null,
      api_key_env: form.api_key_env || null,
      dimension: Number(form.dimension),
      is_active: form.is_active,
      rpm: form.rpm !== '' ? Number(form.rpm) : null,
      tpm: form.tpm !== '' ? Number(form.tpm) : null,
      rpd: form.rpd !== '' ? Number(form.rpd) : null,
    })
    setSaving(false)
    setExpanded(false)
    setForm(emptyForm)
  }

  const isValid = form.provider_type === 'endpoint' ? !!form.endpoint_url : !!form.model

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="w-full rounded-xl border border-dashed border-border bg-card/50 py-4 flex items-center justify-center gap-2 text-sm text-muted-foreground hover:border-foreground/30 hover:text-foreground transition-colors"
      >
        <Plus className="h-4 w-4" />
        {t('admin.addProvider')}
      </button>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{t('admin.newProvider')}</span>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setExpanded(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div>
        <label className={labelClass}>{t('admin.providerMode')}</label>
        <select
          value={form.provider_type}
          onChange={e => setForm(f => ({ ...f, provider_type: e.target.value as 'endpoint' | 'local' }))}
          className={inputClass}
        >
          <option value="endpoint">{t('admin.mode_endpoint')}</option>
          <option value="local">{t('admin.mode_local')}</option>
        </select>
      </div>
      {form.provider_type === 'endpoint' ? (
        <>
          <div>
            <label className={labelClass}>{t('admin.endpointUrl')}</label>
            <input
              className={inputClass}
              value={form.endpoint_url}
              onChange={e => setForm(f => ({ ...f, endpoint_url: e.target.value }))}
              placeholder={t('admin.endpointUrlPlaceholder')}
            />
          </div>
          <div>
            <label className={labelClass}>{t('admin.apiKeyEnvVar')} ({t('admin.optional')})</label>
            <input
              className={inputClass}
              value={form.api_key_env}
              onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
              placeholder={t('admin.apiKeyEnvVarPlaceholder')}
            />
          </div>
        </>
      ) : (
        <div>
          <label className={labelClass}>{t('admin.fastembedModel')}</label>
          <input
            className={inputClass}
            value={form.model}
            onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
            placeholder={t('admin.fastembedModelPlaceholder')}
          />
        </div>
      )}
      <div>
        <label className={labelClass}>{t('admin.dimension')}</label>
        <input
          type="number"
          min={1}
          className={inputClass}
          value={form.dimension}
          onChange={e => setForm(f => ({ ...f, dimension: Number(e.target.value) }))}
        />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {(['rpm', 'tpm', 'rpd'] as const).map(field => (
          <div key={field}>
            <label className={labelClass}>{t(`admin.${field}`)}</label>
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
        <span className="text-sm text-muted-foreground">{t('admin.active')}</span>
      </div>
      <div className="flex gap-2">
        <Button size="sm" onClick={handleAdd} disabled={saving || !isValid}>
          <Check className="h-4 w-4 mr-1" />
          {t('admin.add')}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setExpanded(false)}>
          {t('admin.cancel')}
        </Button>
      </div>
    </div>
  )
}

function ProviderCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-8 w-16 rounded-full" />
      </div>
    </div>
  )
}

function RoleSection({
  role,
  title,
  providers,
  onUpdate,
  onDelete,
  onAdd,
}: {
  role: 'dense' | 'sparse'
  title: string
  providers: RagEmbeddingProvider[]
  onUpdate: (id: string, data: Partial<RagEmbeddingProvider>) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onAdd: (data: Omit<RagEmbeddingProvider, 'id' | 'created_at' | 'updated_at'>) => Promise<void>
}) {
  return (
    <AccordionSection title={title} badge={providers.length}>
      <div className="space-y-2">
        {providers.map(p => (
          <ProviderCard key={p.id} provider={p} onUpdate={onUpdate} onDelete={onDelete} />
        ))}
        <AddProviderCard role={role} onAdd={onAdd} />
      </div>
    </AccordionSection>
  )
}

export default function RagProvidersPage() {
  const { t } = useI18n()
  const router = useRouter()
  const { data: session, status } = useSession()
  const [providers, setProviders] = useState<RagEmbeddingProvider[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (status === 'unauthenticated') router.push('/login')
    if (status === 'authenticated' && (session?.user as any)?.role !== 'admin') router.push('/settings')
  }, [status, session, router])

  const token = (session as any)?.accessToken

  useEffect(() => {
    if (!token) return
    setIsLoading(true)
    fetchRagEmbeddingProviders(token)
      .then(data => setProviders(data))
      .finally(() => setIsLoading(false))
  }, [token])

  const denseProviders = providers.filter(p => p.role === 'dense')
  const sparseProviders = providers.filter(p => p.role === 'sparse')

  async function handleUpdate(id: string, data: Partial<RagEmbeddingProvider>) {
    setError(null)
    const prev = providers
    setProviders(ps => ps.map(p => (p.id === id ? { ...p, ...data } : p)))
    try {
      const updated = await updateRagEmbeddingProvider(id, data, token)
      setProviders(ps => ps.map(p => (p.id === id ? updated : p)))
    } catch (e: any) {
      setProviders(prev)
      if (e?.status === 409) {
        setError(t('admin.ragActiveConflict'))
      } else {
        setError(t('admin.updateFailed'))
      }
    }
  }

  async function handleDelete(id: string) {
    const prev = providers
    setProviders(ps => ps.filter(p => p.id !== id))
    try {
      await deleteRagEmbeddingProvider(id, token)
    } catch {
      setProviders(prev)
      setError(t('admin.deleteFailed'))
    }
  }

  async function handleCreate(data: Omit<RagEmbeddingProvider, 'id' | 'created_at' | 'updated_at'>) {
    setError(null)
    try {
      const created = await createRagEmbeddingProvider(data, token)
      setProviders(ps => [...ps, created])
    } catch (e: any) {
      if (e?.status === 409) {
        setError(t('admin.ragActiveConflict'))
      } else {
        setError(t('admin.createRagProviderFailed'))
      }
    }
  }

  return (
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.ragProviders')}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('admin.ragProvidersDesc')}
        </p>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {isLoading ? (
        <div className="space-y-4">
          {[0, 1].map(i => (
            <div key={i} className="rounded-xl border border-border overflow-hidden">
              <div className="px-5 py-4 bg-card flex items-center justify-between">
                <Skeleton className="h-5 w-24" />
                <Skeleton className="h-4 w-4" />
              </div>
              <div className="px-4 pb-4 pt-2 space-y-3 bg-muted/20">
                <ProviderCardSkeleton />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <RoleSection
            role="dense"
            title={t('admin.denseEmbedding')}
            providers={denseProviders}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onAdd={handleCreate}
          />
          <RoleSection
            role="sparse"
            title={t('admin.sparseEmbedding')}
            providers={sparseProviders}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onAdd={handleCreate}
          />
        </div>
      )}
    </div>
  )
}
