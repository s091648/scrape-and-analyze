'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Plus, X, Lock } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { useTopic, useI18n } from '@/lib/providers'
import {
  fetchTagGroups, fetchPendingSuggestions, createTagGroup, moveTag, batchMoveTags,
  type TagGroupOut, type SuggestionOut, type TagGroupCreate, type TagOut,
} from '@/lib/api/tags'
import { TagGroupCard } from '@/components/features/tags/tag-group-card'
import { PendingSuggestions } from '@/components/features/tags/pending-suggestions'
import { PendingChangesPanel } from '@/components/features/tags/pending-changes-panel'
import {
  DndContext, DragOverlay, MouseSensor, TouchSensor,
  useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from '@dnd-kit/core'

// ── Fake data shown behind paywall for unauthenticated users ──────────────────
const FAKE_GROUPS: TagGroupOut[] = [
  {
    id: 'fake-1', name: 'research_methods', display_name: 'Research Methods',
    description: 'Core methodologies and algorithmic approaches.', color_hex: '#6366f1', topic_id: '',
    tags: [
      { id: 'f1', name: 'Transformer', article_count: 48 },
      { id: 'f2', name: 'Diffusion Model', article_count: 31 },
      { id: 'f3', name: 'Reinforcement Learning', article_count: 27 },
      { id: 'f4', name: 'Graph Neural Network', article_count: 19 },
    ],
  },
  {
    id: 'fake-2', name: 'applications', display_name: 'Applications',
    description: 'Applied domains and downstream tasks.', color_hex: '#10b981', topic_id: '',
    tags: [
      { id: 'f5', name: 'Computer Vision', article_count: 35 },
      { id: 'f6', name: 'Natural Language Processing', article_count: 29 },
      { id: 'f7', name: 'Robotics', article_count: 14 },
    ],
  },
  {
    id: 'fake-3', name: 'evaluation', display_name: 'Evaluation & Benchmarks',
    description: null, color_hex: '#f59e0b', topic_id: '',
    tags: [
      { id: 'f8', name: 'MMLU', article_count: 22 },
      { id: 'f9', name: 'HumanEval', article_count: 17 },
      { id: 'f10', name: 'HELM', article_count: 11 },
    ],
  },
]

// ── Add Group Dialog ──────────────────────────────────────────────────────────
function AddGroupDialog({
  topicId,
  token,
  onCreated,
  onClose,
}: {
  topicId: string
  token: string
  onCreated: (group: TagGroupOut) => void
  onClose: () => void
}) {
  const { t } = useI18n()
  const [form, setForm] = useState<TagGroupCreate>({
    name: '', display_name: '', topic_id: topicId, color_hex: '', description: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name.trim() || !form.display_name.trim()) return
    setSaving(true)
    setError('')
    try {
      const body: TagGroupCreate = {
        name: form.name.trim(),
        display_name: form.display_name.trim(),
        topic_id: topicId,
        ...(form.color_hex?.trim() ? { color_hex: form.color_hex.trim() } : {}),
        ...(form.description?.trim() ? { description: form.description.trim() } : {}),
      }
      const created = await createTagGroup(body, token)
      onCreated(created)
    } catch (err: any) {
      setError(err.message ?? 'Error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <form
        className="bg-card border border-border rounded-xl p-6 w-full max-w-sm space-y-4 shadow-lg"
        onClick={e => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">{t('tags.addGroup')}</h2>
          <button type="button" onClick={onClose}><X className="h-4 w-4 text-muted-foreground" /></button>
        </div>

        {[
          { key: 'name', label: t('tags.groupName'), required: true },
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
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>{t('tags.keepBoth')}</Button>
          <Button type="submit" size="sm" disabled={saving}>{t('tags.createGroup')}</Button>
        </div>
      </form>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function TagsPage() {
  const { data: session, status } = useSession()
  const token = (session as any)?.accessToken as string | undefined
  const isAdmin = (session?.user as any)?.role === 'admin'
  const { selectedTopic } = useTopic()
  const { t } = useI18n()

  const isGuest = status === 'unauthenticated'

  const [groups, setGroups] = useState<TagGroupOut[]>([])
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddGroup, setShowAddGroup] = useState(false)

  interface PendingMove {
    tag: TagOut
    fromGroupId: string
    toGroupId: string
    toGroupName: string
  }

  const [pendingMoves, setPendingMoves] = useState<Map<string, PendingMove>>(new Map())
  const [activeDragTag, setActiveDragTag] = useState<TagOut | null>(null)
  const [confirming, setConfirming] = useState(false)

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
  )

  function handleDragStart({ active }: DragStartEvent) {
    setActiveDragTag(active.data.current?.tag ?? null)
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveDragTag(null)
    if (!over) return

    const tag: TagOut = active.data.current?.tag
    const fromGroupId: string = active.data.current?.groupId
    const toGroupId = String(over.id)
    if (!tag || fromGroupId === toGroupId) return

    const toGroup = groups.find(g => g.id === toGroupId)
    if (!toGroup) return

    const existingPending = pendingMoves.get(tag.id)
    const originalFromGroupId = existingPending?.fromGroupId ?? fromGroupId

    if (toGroupId === originalFromGroupId) {
      setGroups(prev => prev.map(g =>
        g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
        g.id === originalFromGroupId ? { ...g, tags: [...g.tags, tag] } : g
      ))
      setPendingMoves(prev => { const next = new Map(prev); next.delete(tag.id); return next })
      return
    }

    setGroups(prev => prev.map(g =>
      g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
      g.id === toGroupId ? { ...g, tags: [...g.tags, tag] } : g
    ))

    setPendingMoves(prev => new Map(prev).set(tag.id, {
      tag,
      fromGroupId: originalFromGroupId,
      toGroupId,
      toGroupName: toGroup.name,
    }))
  }

  async function handleConfirm() {
    if (!token || pendingMoves.size === 0) return
    setConfirming(true)
    const moves = [...pendingMoves.values()]

    if (moves.length === 1) {
      const m = moves[0]
      try {
        await moveTag(m.tag.id, m.toGroupName, token)
        setPendingMoves(new Map())
      } catch {
        // leave in pending state for retry
      }
    } else {
      try {
        const result = await batchMoveTags(
          moves.map(m => ({ tag_id: m.tag.id, tag_group_name: m.toGroupName })),
          token,
        )
        const failedIds = new Set(result.failed.map(f => f.tag_id))
        setPendingMoves(prev => {
          const next = new Map(prev)
          result.succeeded.forEach(id => next.delete(id))
          return next
        })
        if (result.failed.length > 0) {
          setGroups(prev => {
            let next = prev.map(g => ({ ...g, tags: [...g.tags] }))
            for (const m of moves) {
              if (!failedIds.has(m.tag.id)) continue
              next = next
                .map(g => g.id === m.toGroupId ? { ...g, tags: g.tags.filter(t => t.id !== m.tag.id) } : g)
                .map(g => g.id === m.fromGroupId ? { ...g, tags: [...g.tags, m.tag] } : g)
            }
            return next
          })
        }
      } catch {
        // leave all pending for retry
      }
    }
    setConfirming(false)
  }

  function handleDiscard() {
    const moves = [...pendingMoves.values()]
    setGroups(prev => {
      let next = prev.map(g => ({ ...g, tags: [...g.tags] }))
      for (const m of moves) {
        next = next
          .map(g => g.id === m.toGroupId ? { ...g, tags: g.tags.filter(t => t.id !== m.tag.id) } : g)
          .map(g => g.id === m.fromGroupId ? { ...g, tags: [...g.tags, m.tag] } : g)
      }
      return next
    })
    setPendingMoves(new Map())
  }

  useEffect(() => {
    if (isGuest) { setLoading(false); return }
    setLoading(true)
    const topicId = selectedTopic?.id
    Promise.all([
      fetchTagGroups(topicId),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ])
      .then(([g, s]) => { setGroups(g); setSuggestions(s) })
      .finally(() => setLoading(false))
  }, [selectedTopic?.id, isAdmin, token, isGuest])

  return (
    <div className="container mx-auto px-6 pt-24 pb-16 max-w-4xl space-y-8">
      <div className="border-b border-border pb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{t('tags.title')}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t('tags.description')}
              {isAdmin && t('tags.adminDesc')}
            </p>
          </div>
          {isAdmin && token && (
            <Button
              size="sm" variant="outline" className="shrink-0 gap-1.5"
              onClick={() => {
                if (!selectedTopic?.id) {
                  alert(t('tags.noTopicSelected'))
                  return
                }
                setShowAddGroup(true)
              }}
            >
              <Plus className="h-3.5 w-3.5" />
              {t('tags.addGroup')}
            </Button>
          )}
        </div>
      </div>

      {/* ── Paywall for guests ── */}
      {isGuest ? (
        <div className="relative">
          {/* Fake groups behind blur */}
          <div className="space-y-4 select-none pointer-events-none">
            {FAKE_GROUPS.map(group => (
              <TagGroupCard
                key={group.id}
                group={group}
                isAdmin={false}
                pendingIncomingTagIds={new Set()}
                onDeleted={() => {}}
                onTagRenamed={() => {}}
                onTagDeleted={() => {}}
                onGroupUpdated={() => {}}
              />
            ))}
          </div>

          {/* Blur + lock overlay */}
          <div className="absolute inset-0 backdrop-blur-sm bg-background/60 flex flex-col items-center justify-center gap-4 rounded-xl">
            <div className="flex items-center justify-center h-14 w-14 rounded-full border border-border bg-background shadow-sm">
              <Lock className="h-6 w-6 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1.5">
              <p className="text-sm font-medium">{t('tags.signInToExplore')}</p>
              <p className="text-sm text-muted-foreground">
                <Link href="/login" className="font-medium text-primary underline underline-offset-4">
                  {t('login.signIn')}
                </Link>
                {' '}{t('tags.signInToAccess')}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <>
          {isAdmin && suggestions.length > 0 && (
            <PendingSuggestions
              suggestions={suggestions}
              token={token!}
              onResolved={id => {
                setSuggestions(prev => prev.filter(s => s.id !== id))
                fetchTagGroups(selectedTopic?.id).then(setGroups)
              }}
            />
          )}

          {loading ? (
            <div className="space-y-4">
              {[0, 1, 2].map(i => (
                <div key={i} className="rounded-xl border border-border bg-card p-5 space-y-3">
                  <Skeleton className="h-4 w-32" />
                  <div className="flex gap-2">
                    <Skeleton className="h-6 w-20 rounded-full" />
                    <Skeleton className="h-6 w-16 rounded-full" />
                    <Skeleton className="h-6 w-24 rounded-full" />
                  </div>
                </div>
              ))}
            </div>
          ) : groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('tags.noGroups')}</p>
          ) : (
            <DndContext
              sensors={sensors}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <div className="space-y-4">
                {groups.map(group => {
                  const pendingIncomingTagIds = new Set(
                    [...pendingMoves.values()]
                      .filter(m => m.toGroupId === group.id)
                      .map(m => m.tag.id)
                  )
                  return (
                    <TagGroupCard
                      key={group.id}
                      group={group}
                      isAdmin={isAdmin}
                      token={token}
                      pendingIncomingTagIds={pendingIncomingTagIds}
                      onDeleted={groupId => setGroups(prev => prev.filter(g => g.id !== groupId))}
                      onTagRenamed={(groupId, tagId, name) => setGroups(prev =>
                        prev.map(g => g.id === groupId
                          ? { ...g, tags: g.tags.map(t => t.id === tagId ? { ...t, name } : t) }
                          : g
                        )
                      )}
                      onTagDeleted={(groupId, tagId) => setGroups(prev =>
                        prev.map(g => g.id === groupId
                          ? { ...g, tags: g.tags.filter(t => t.id !== tagId) }
                          : g
                        )
                      )}
                      onGroupUpdated={(groupId, updated) => setGroups(prev =>
                        prev.map(g => g.id === groupId ? { ...g, ...updated } : g)
                      )}
                    />
                  )
                })}
              </div>
              <DragOverlay>
                {activeDragTag && (
                  <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-primary bg-card text-xs shadow-md cursor-grabbing">
                    {activeDragTag.name}
                    <span className="text-muted-foreground tabular-nums">
                      ({activeDragTag.article_count})
                    </span>
                  </div>
                )}
              </DragOverlay>
            </DndContext>
          )}
          {pendingMoves.size > 0 && (
            <PendingChangesPanel
              count={pendingMoves.size}
              confirming={confirming}
              onConfirm={handleConfirm}
              onDiscard={handleDiscard}
            />
          )}
        </>
      )}

      {showAddGroup && selectedTopic?.id && token && (
        <AddGroupDialog
          topicId={selectedTopic.id}
          token={token}
          onCreated={group => {
            setGroups(prev => [...prev, group])
            setShowAddGroup(false)
          }}
          onClose={() => setShowAddGroup(false)}
        />
      )}
    </div>
  )
}
