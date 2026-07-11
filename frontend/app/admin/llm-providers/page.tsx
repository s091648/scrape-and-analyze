'use client'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { Pencil, X, Check, Plus, HelpCircle, GripVertical } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AccordionSection } from '@/components/ui/accordion-section'
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  type LlmProvider,
  fetchLlmProviders,
  createLlmProvider,
  updateLlmProvider,
  deleteLlmProvider,
  reorderLlmProviders,
} from '@/lib/api'
import { useI18n } from '@/lib/providers'

const PROVIDER_NAMES = ['gemini', 'claude', 'openrouter', 'huggingface'] as const
const PROVIDER_TYPES = ['llm', 'embedding', 'multimodal'] as const

// ── Sortable Provider Card ────────────────────────────────────────────────────

function SortableProviderCard({
  provider,
  onUpdate,
  onDelete,
}: {
  provider: LlmProvider
  onUpdate: (id: string, data: Partial<LlmProvider>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: provider.name,
    model: provider.model,
    api_key_env: provider.api_key_env,
    is_active: provider.is_active,
    type: provider.type ?? 'llm',
    rpm: provider.rpm ?? '',
    tpm: provider.tpm ?? '',
    rpd: provider.rpd ?? '',
  })

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: provider.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  const inputClass =
    'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
  const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

  async function handleSave() {
    setSaving(true)
    await onUpdate(provider.id, {
      name: form.name,
      model: form.model,
      api_key_env: form.api_key_env,
      is_active: form.is_active,
      type: form.type as 'llm' | 'embedding' | 'multimodal',
      rpm: form.rpm !== '' ? Number(form.rpm) : null,
      tpm: form.tpm !== '' ? Number(form.tpm) : null,
      rpd: form.rpd !== '' ? Number(form.rpd) : null,
    })
    setSaving(false)
    setEditing(false)
  }

  return (
    <>
      <div ref={setNodeRef} style={style} className="rounded-xl border border-border bg-card p-5 space-y-3">
        {editing ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">{t('admin.editProvider')}</span>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass}>{t('admin.provider')}</label>
                <select
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  className={inputClass}
                >
                  {PROVIDER_NAMES.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className={labelClass}>{t('admin.providerType')}</label>
                <select
                  value={form.type}
                  onChange={e => setForm(f => ({ ...f, type: e.target.value as 'llm' | 'embedding' | 'multimodal' }))}
                  className={inputClass}
                >
                  {PROVIDER_TYPES.map(pt => (
                    <option key={pt} value={pt}>{t(`admin.type_${pt}`)}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className={labelClass}>{t('admin.model')}</label>
              <input
                className={inputClass}
                value={form.model}
                onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                placeholder={t('admin.modelPlaceholder')}
              />
            </div>
            <div>
              <label className={labelClass}>{t('admin.apiKeyEnvVar')}</label>
              <input
                className={inputClass}
                value={form.api_key_env}
                onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
                placeholder={t('admin.apiKeyEnvVarPlaceholder')}
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
          <div className="flex items-start gap-2">
            <button
              {...attributes}
              {...listeners}
              className="mt-1 cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground shrink-0"
              aria-label={t('admin.dragToReorder')}
            >
              <GripVertical className="h-5 w-5" />
            </button>
            <div className="flex-1 space-y-1">
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
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                {t('admin.callsInLast24h', { count: provider.usage_24h })}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <HelpCircle className="h-3 w-3 shrink-0 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent>
                    {t('admin.callsInLast24hTooltip')}
                  </TooltipContent>
                </Tooltip>
              </p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
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
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t('admin.deleteProvider')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('admin.deleteProviderConfirm', { model: provider.model })}
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

// ── Add Provider Card ─────────────────────────────────────────────────────────

function AddProviderCard({ onAdd, nextPriority, defaultType }: {
  onAdd: (data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>) => Promise<void>
  nextPriority: number
  defaultType: 'llm' | 'embedding' | 'multimodal'
}) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const emptyForm = {
    name: 'gemini' as string,
    model: '',
    api_key_env: '',
    is_active: true,
    type: defaultType,
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
      priority: nextPriority,
      is_active: form.is_active,
      type: form.type as 'llm' | 'embedding' | 'multimodal',
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
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>{t('admin.provider')}</label>
          <select
            value={form.name}
            onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            className={inputClass}
          >
            {PROVIDER_NAMES.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className={labelClass}>{t('admin.providerType')}</label>
          <select
            value={form.type}
            onChange={e => setForm(f => ({ ...f, type: e.target.value as 'llm' | 'embedding' | 'multimodal' }))}
            className={inputClass}
          >
            {PROVIDER_TYPES.map(pt => (
              <option key={pt} value={pt}>{t(`admin.type_${pt}`)}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className={labelClass}>{t('admin.model')}</label>
        <input
          className={inputClass}
          value={form.model}
          onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
          placeholder={t('admin.modelPlaceholder')}
        />
      </div>
      <div>
        <label className={labelClass}>{t('admin.apiKeyEnvVar')}</label>
        <input
          className={inputClass}
          value={form.api_key_env}
          onChange={e => setForm(f => ({ ...f, api_key_env: e.target.value }))}
          placeholder={t('admin.apiKeyEnvVarPlaceholder')}
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
        <Button size="sm" onClick={handleAdd} disabled={saving || !form.model || !form.api_key_env}>
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

// ── Provider Section ──────────────────────────────────────────────────────────

function ProviderSection({
  title,
  type,
  providers,
  sensors,
  onDragEnd,
  onUpdate,
  onDelete,
  onAdd,
  nextPriority,
}: {
  title: string
  type: 'llm' | 'embedding' | 'multimodal'
  providers: LlmProvider[]
  sensors: ReturnType<typeof useSensors>
  onDragEnd: (event: DragEndEvent) => Promise<void>
  onUpdate: (id: string, data: Partial<LlmProvider>) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onAdd: (data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>) => Promise<void>
  nextPriority: number
}) {
  const [isDragging, setIsDragging] = useState(false)

  return (
    <AccordionSection title={title} badge={providers.length}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={() => setIsDragging(true)}
        onDragEnd={async (event) => {
          setIsDragging(false)
          await onDragEnd(event)
        }}
        onDragCancel={() => setIsDragging(false)}
      >
        <div
          className={[
            'rounded-lg transition-all duration-150 space-y-2',
            isDragging
              ? 'ring-2 ring-dashed ring-primary/50 bg-primary/5 p-2'
              : '',
          ].join(' ')}
        >
          <SortableContext
            items={providers.map(p => p.id)}
            strategy={verticalListSortingStrategy}
          >
            {providers.map(p => (
              <SortableProviderCard
                key={p.id}
                provider={p}
                onUpdate={onUpdate}
                onDelete={onDelete}
              />
            ))}
          </SortableContext>
        </div>
      </DndContext>
      <AddProviderCard onAdd={onAdd} nextPriority={nextPriority} defaultType={type} />
    </AccordionSection>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function LlmProvidersPage() {
  const { t } = useI18n()
  const router = useRouter()
  const { data: session, status } = useSession()
  const [providers, setProviders] = useState<LlmProvider[]>([])
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
    fetchLlmProviders(token)
      .then(data => setProviders(data.sort((a, b) => a.priority - b.priority)))
      .finally(() => setIsLoading(false))
  }, [token])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const llmProviders = providers.filter(p => (p.type ?? 'llm') === 'llm').sort((a, b) => a.priority - b.priority)
  const embeddingProviders = providers.filter(p => p.type === 'embedding').sort((a, b) => a.priority - b.priority)
  const multimodalProviders = providers.filter(p => p.type === 'multimodal').sort((a, b) => a.priority - b.priority)

  function makeDragEndHandler(type: 'llm' | 'embedding' | 'multimodal') {
    return async function handleDragEnd(event: DragEndEvent) {
      const { active, over } = event
      if (!over || active.id === over.id) return

      const typeProviders = providers
        .filter(p => (p.type ?? 'llm') === type)
        .sort((a, b) => a.priority - b.priority)

      const oldIndex = typeProviders.findIndex(p => p.id === active.id)
      const newIndex = typeProviders.findIndex(p => p.id === over.id)
      if (oldIndex === -1 || newIndex === -1) return

      const reordered = [...typeProviders]
      const [moved] = reordered.splice(oldIndex, 1)
      reordered.splice(newIndex, 0, moved)

      const withNewPriorities = reordered.map((p, i) => ({ ...p, priority: i + 1 }))
      const snapshot = providers
      setProviders([
        ...providers.filter(p => (p.type ?? 'llm') !== type),
        ...withNewPriorities,
      ])

      try {
        const result = await reorderLlmProviders(
          withNewPriorities.map(p => ({ id: p.id, priority: p.priority })),
          token,
        )
        setProviders(prev => [
          ...prev.filter(p => (p.type ?? 'llm') !== type),
          ...result.filter(p => (p.type ?? 'llm') === type).sort((a, b) => a.priority - b.priority),
        ])
      } catch {
        setProviders(snapshot)
        setError(t('admin.reorderFailed'))
      }
    }
  }

  async function handleUpdate(id: string, data: Partial<LlmProvider>) {
    setError(null)
    const prevProviders = providers
    setProviders(prev => prev.map(p => (p.id === id ? { ...p, ...data } : p)))
    try {
      await updateLlmProvider(id, data, token)
    } catch (e: any) {
      setProviders(prevProviders)
      if (e?.status === 409) {
        setError(t('admin.priorityConflict', { priority: providers.find(x => x.id === id)?.priority ?? '?' }))
      } else {
        setError(t('admin.updateFailed'))
      }
    }
  }

  async function handleDelete(id: string) {
    const prevProviders = providers
    setProviders(prev => prev.filter(p => p.id !== id))
    try {
      await deleteLlmProvider(id, token)
    } catch {
      setProviders(prevProviders)
      setError(t('admin.deleteFailed'))
    }
  }

  async function handleCreate(data: Omit<LlmProvider, 'id' | 'usage_24h' | 'created_at' | 'updated_at'>) {
    setError(null)
    try {
      const created = await createLlmProvider(data, token)
      setProviders(prev => [...prev, created].sort((a, b) => a.priority - b.priority))
    } catch (e: any) {
      if (e?.status === 409) {
        setError(t('admin.priorityConflict', { priority: data.priority }))
      }
    }
  }

  const llmNextPriority = llmProviders.length > 0 ? Math.max(...llmProviders.map(p => p.priority)) + 1 : 1
  const embeddingNextPriority = embeddingProviders.length > 0 ? Math.max(...embeddingProviders.map(p => p.priority)) + 1 : 1
  const multimodalNextPriority = multimodalProviders.length > 0 ? Math.max(...multimodalProviders.map(p => p.priority)) + 1 : 1

  return (
    <TooltipProvider>
    <div className="max-w-3xl space-y-10">
      <div className="border-b border-border pb-6">
        <h1 className="text-2xl font-bold">{t('admin.llmProviders')}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t('admin.llmProvidersDesc')}
        </p>
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

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
                <ProviderCardSkeleton />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <ProviderSection
            title={t('admin.type_llm')}
            type="llm"
            providers={llmProviders}
            sensors={sensors}
            onDragEnd={makeDragEndHandler('llm')}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onAdd={handleCreate}
            nextPriority={llmNextPriority}
          />
          <ProviderSection
            title={t('admin.type_embedding')}
            type="embedding"
            providers={embeddingProviders}
            sensors={sensors}
            onDragEnd={makeDragEndHandler('embedding')}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onAdd={handleCreate}
            nextPriority={embeddingNextPriority}
          />
          <ProviderSection
            title={t('admin.type_multimodal')}
            type="multimodal"
            providers={multimodalProviders}
            sensors={sensors}
            onDragEnd={makeDragEndHandler('multimodal')}
            onUpdate={handleUpdate}
            onDelete={handleDelete}
            onAdd={handleCreate}
            nextPriority={multimodalNextPriority}
          />
        </div>
      )}
    </div>
    </TooltipProvider>
  )
}
