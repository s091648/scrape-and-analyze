'use client'
import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Network, Plus, X, Lock, GitMerge, Tags, Search } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useTopic, useI18n } from '@/lib/providers'
import {
  fetchTagGroups, fetchPendingSuggestions, createTagGroup, moveTag, batchMoveTags,
  type TagGroupOut, type SuggestionOut, type TagGroupCreate, type TagOut,
} from '@/lib/api/tags'
import { TagGroupCard } from '@/components/features/tags/tag-group-card'
import { PendingSuggestions } from '@/components/features/tags/pending-suggestions'
import { PendingChangesPanel } from '@/components/features/tags/pending-changes-panel'
import { MergeGroupDialog } from '@/components/features/tags/merge-group-dialog'
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
    similar_groups: [
      { id: 'fake-2', similarity_score: 0.75 },
      { id: 'fake-3', similarity_score: 0.6 },
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
    similar_groups: [
      { id: 'fake-1', similarity_score: 0.75 },
      { id: 'fake-3', similarity_score: 0.6 },
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
    similar_groups: [
      { id: 'fake-1', similarity_score: 0.75 },
      { id: 'fake-2', similarity_score: 0.6 },
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
                onChange={e => setForm(prev => ({ ...prev, [key]: e.target.value }))}
                required={required}
              />
            )}
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

// ── Similarity Lines ──────────────────────────────────────────────────────────
interface LineData {
  x1: number; y1: number; x2: number; y2: number
  score: number; key: string; groupAId: string; groupBId: string
  side: 'right' | 'left'
  pivot: number     // x of the vertical segment (rx for right, lx for left)
  xTooltip: number  // x anchor for the hover tooltip
}

function SimilarityLines({
  groups,
  groupRefs,
  onMergeRequested,
}: {
  groups: TagGroupOut[]
  groupRefs: React.RefObject<Map<string, HTMLDivElement>>
  onMergeRequested: (groupAId: string, groupBId: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [lines, setLines] = useState<LineData[]>([])
  const [totalHeight, setTotalHeight] = useState(0)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)

  function scoreToStub(score: number) {
    const t = Math.min(1, Math.max(0, (score - 0.9) / 0.1))
    return Math.round(164 - t * 156) // score=0.9→164px, score=1.0→8px
  }

  const computeLines = useCallback(() => {
    const container = containerRef.current
    if (!container) return

    const parent = container.parentElement
    if (parent) setTotalHeight(parent.scrollHeight)

    const containerRect = container.getBoundingClientRect()
    type Raw = {
      y1: number; y2: number; score: number; key: string; groupAId: string; groupBId: string
      x1R: number; x2R: number; x1L: number; x2L: number
    }
    const raw: Raw[] = []
    const seen = new Set<string>()

    for (const group of groups) {
      for (const sim of group.similar_groups) {
        const pairKey = [group.id, sim.id].sort().join('-')
        if (seen.has(pairKey)) continue
        seen.add(pairKey)

        const fromEl = groupRefs.current?.get(group.id)
        const toEl = groupRefs.current?.get(sim.id)
        if (!fromEl || !toEl) continue

        const fromRect = fromEl.getBoundingClientRect()
        const toRect = toEl.getBoundingClientRect()

        raw.push({
          y1: fromRect.top + fromRect.height / 2 - containerRect.top,
          y2: toRect.top + toRect.height / 2 - containerRect.top,
          score: sim.similarity_score,
          key: pairKey,
          groupAId: group.id,
          groupBId: sim.id,
          x1R: fromRect.right - containerRect.left,
          x2R: toRect.right - containerRect.left,
          x1L: fromRect.left - containerRect.left,
          x2L: toRect.left - containerRect.left,
        })
      }
    }

    // Sort by score desc so adjacent pairs (most similar scores) alternate sides.
    // Even index → right side, odd index → left side.
    // This guarantees that pairs most likely to share a stub length go to opposite sides.
    raw.sort((a, b) => b.score - a.score)

    setLines(raw.map((l, i) => {
      const side: 'right' | 'left' = i % 2 === 0 ? 'right' : 'left'
      const stub = scoreToStub(l.score)
      const xR = Math.max(l.x1R, l.x2R) // rightmost right-edge (for tooltip anchor)
      if (side === 'right') {
        const pivot = xR + stub
        return {
          x1: l.x1R, y1: l.y1, x2: l.x2R, y2: l.y2,
          score: l.score, key: l.key, groupAId: l.groupAId, groupBId: l.groupBId,
          side, pivot, xTooltip: pivot + 8,
        }
      } else {
        const pivot = Math.min(l.x1L, l.x2L) - stub
        return {
          x1: l.x1L, y1: l.y1, x2: l.x2L, y2: l.y2,
          score: l.score, key: l.key, groupAId: l.groupAId, groupBId: l.groupBId,
          side, pivot,
          xTooltip: pivot - 8,
        }
      }
    }))
  }, [groups, groupRefs])

  useEffect(() => {
    computeLines()
    const observer = new ResizeObserver(computeLines)
    const parent = containerRef.current?.parentElement
    if (parent) observer.observe(parent)
    return () => observer.disconnect()
  }, [computeLines])

  const hoveredLine = hoveredKey ? lines.find(l => l.key === hoveredKey) : null
  const hoveredGroupA = hoveredLine ? groups.find(g => g.id === hoveredLine.groupAId) : null
  const hoveredGroupB = hoveredLine ? groups.find(g => g.id === hoveredLine.groupBId) : null

  // Tip at (x,y) pointing LEFT — used for right-side lines (into card right edge)
  function arrowLeft(x: number, y: number, size = 8) {
    return `M ${x} ${y} L ${x + size} ${y - size * 0.5} L ${x + size} ${y + size * 0.5} Z`
  }

  // Tip at (x,y) pointing RIGHT — used for left-side lines (into card left edge)
  function arrowRight(x: number, y: number, size = 8) {
    return `M ${x} ${y} L ${x - size} ${y - size * 0.5} L ${x - size} ${y + size * 0.5} Z`
  }

  return (
    <div
      ref={containerRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{ width: '100%', height: totalHeight }}
    >
      <svg
        width="100%"
        height={totalHeight}
        className="absolute inset-0 overflow-visible"
        style={{ pointerEvents: 'none' }}
      >
        {lines.map(l => {
          const isHovered = hoveredKey === l.key
          const t = Math.min(1, Math.max(0, (l.score - 0.9) / 0.1))
          const baseOpacity = 0.15 + t * 0.85
          const opacity = isHovered ? 1 : baseOpacity
          const strokeWidth = isHovered ? 3 : 0.75 + t * 2.25
          const color = 'rgb(251,191,36)'
          const d = `M ${l.x1} ${l.y1} H ${l.pivot} V ${l.y2} H ${l.x2}`

          return (
            <g
              key={l.key}
              opacity={opacity}
              style={{ pointerEvents: 'auto' }}
              onMouseEnter={() => setHoveredKey(l.key)}
              onMouseLeave={() => setHoveredKey(null)}
            >
              <path d={d} fill="none" stroke="transparent" strokeWidth={16} />
              <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth} />
              {l.side === 'right' ? (
                <>
                  <path d={arrowLeft(l.x1, l.y1)} fill={color} stroke="none" />
                  <path d={arrowLeft(l.x2, l.y2)} fill={color} stroke="none" />
                </>
              ) : (
                <>
                  <path d={arrowRight(l.x1, l.y1)} fill={color} stroke="none" />
                  <path d={arrowRight(l.x2, l.y2)} fill={color} stroke="none" />
                </>
              )}
              {!isHovered && (() => {
                const midY = (l.y1 + l.y2) / 2
                const label = `${(l.score * 100).toFixed(0)}%`
                const pillW = label.length <= 3 ? 28 : 34
                const pillH = 15
                return (
                  <g>
                    <rect
                      x={l.pivot - pillW / 2} y={midY - pillH / 2}
                      width={pillW} height={pillH} rx={pillH / 2}
                      fill="rgb(254,243,199)" stroke="rgb(251,191,36)" strokeWidth={0.75}
                    />
                    <text
                      x={l.pivot} y={midY}
                      textAnchor="middle" dominantBaseline="middle"
                      fontSize={9} fontWeight="600" fill="rgb(146,64,14)"
                    >
                      {label}
                    </text>
                  </g>
                )
              })()}
            </g>
          )
        })}
      </svg>

      {hoveredLine && hoveredGroupA && hoveredGroupB && (() => {
        const midY = (hoveredLine.y1 + hoveredLine.y2) / 2
        return (
          <div
            className="absolute z-20 pointer-events-auto"
            style={{ left: hoveredLine.xTooltip, top: midY, transform: hoveredLine.side === 'left' ? 'translate(-100%, -50%)' : 'translateY(-50%)' }}
            onMouseEnter={() => setHoveredKey(hoveredLine.key)}
            onMouseLeave={() => setHoveredKey(null)}
          >
            <div className="bg-card border border-border rounded-lg px-3 py-2 shadow-md text-xs whitespace-nowrap flex flex-col items-center gap-1 min-w-max">
              <span className="font-medium">
                {hoveredGroupA.display_name} ↔ {hoveredGroupB.display_name}
              </span>
              <span className="text-muted-foreground">
                {(hoveredLine.score * 100).toFixed(0)}% similarity
              </span>
              <button
                className="flex items-center gap-1 text-primary hover:underline mt-0.5"
                onClick={() => onMergeRequested(hoveredLine.groupAId, hoveredLine.groupBId)}
              >
                <GitMerge className="h-3 w-3" />
                Merge
              </button>
            </div>
          </div>
        )
      })()}
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

  const [autoTagGroups, setAutoTagGroups] = useState<boolean>(
    selectedTopic?.auto_tag_groups ?? true
  )

  const [showSimilarities, setShowSimilarities] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const groupRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  const filteredGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return groups
    return groups.filter(g =>
      g.display_name.toLowerCase().includes(q) ||
      g.name.toLowerCase().includes(q) ||
      g.tags.some(t => t.name.toLowerCase().includes(q))
    )
  }, [groups, searchQuery])

  // ── Merge state ──
  const [mergingGroupId, setMergingGroupId] = useState<string | null>(null)
  const [mergeGroupPair, setMergeGroupPair] = useState<[TagGroupOut, TagGroupOut] | null>(null)

  // Sync autoTagGroups when topic changes
  useEffect(() => {
    setAutoTagGroups(selectedTopic?.auto_tag_groups ?? true)
  }, [selectedTopic?.id])

  async function handleAutoTagGroupsToggle(checked: boolean) {
    if (!selectedTopic || !token) return
    setAutoTagGroups(checked)
    try {
      const { updateTopic } = await import('@/lib/api/topics')
      await updateTopic(selectedTopic.id, { auto_tag_groups: checked }, token)
    } catch {
      setAutoTagGroups(!checked)
    }
  }

  interface PendingMove {
    tag: TagOut
    fromGroupId: string
    toGroupId: string
    toGroupName: string
  }

  const [pendingMoves, setPendingMoves] = useState<Map<string, PendingMove>>(new Map())
  const [activeDragTag, setActiveDragTag] = useState<TagOut | null>(null)
  const [activeDragGroup, setActiveDragGroup] = useState<TagGroupOut | null>(null)
  const [confirming, setConfirming] = useState(false)

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
  )

  function handleDragStart({ active }: DragStartEvent) {
    if (active.data.current?.type === 'group') {
      setActiveDragGroup(active.data.current.group ?? null)
    } else {
      setActiveDragTag(active.data.current?.tag ?? null)
    }
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveDragTag(null)
    setActiveDragGroup(null)
    if (!over) return

    // Group merge via drag
    if (active.data.current?.type === 'group') {
      const draggedGroup: TagGroupOut = active.data.current.group
      const targetGroupId = String(over.id)
      if (draggedGroup.id === targetGroupId) return
      const targetGroup = groups.find(g => g.id === targetGroupId)
      if (!targetGroup) return
      setMergeGroupPair([draggedGroup, targetGroup])
      return
    }

    // Tag move
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

  // ── Merge handlers ──
  function handleMergeRequested(groupId: string) {
    setMergingGroupId(prev => prev === groupId ? null : groupId)
  }

  function handleMergeTargetSelected(targetGroupId: string) {
    if (!mergingGroupId) return
    const groupA = groups.find(g => g.id === mergingGroupId)
    const groupB = groups.find(g => g.id === targetGroupId)
    if (!groupA || !groupB) return
    setMergeGroupPair([groupA, groupB])
    setMergingGroupId(null)
  }

  function handleMergeFromLine(groupAId: string, groupBId: string) {
    const groupA = groups.find(g => g.id === groupAId)
    const groupB = groups.find(g => g.id === groupBId)
    if (!groupA || !groupB) return
    setMergeGroupPair([groupA, groupB])
  }

  function handleMerged(result: TagGroupOut) {
    if (!mergeGroupPair) return
    const [groupA, groupB] = mergeGroupPair
    setGroups(prev => {
      const idxA = prev.findIndex(g => g.id === groupA.id)
      return prev
        .map((g, i) => i === idxA ? result : g)
        .filter(g => g.id !== groupB.id)
    })
    setMergeGroupPair(null)
  }

  useEffect(() => {
    if (isGuest) { setLoading(false); return }
    setLoading(true)
    const topicId = selectedTopic?.id
    Promise.all([
      fetchTagGroups(topicId, isAdmin && showSimilarities),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ])
      .then(([g, s]) => { setGroups(g); setSuggestions(s) })
      .finally(() => setLoading(false))
  }, [selectedTopic?.id, isAdmin, token, isGuest, showSimilarities])

  // Cancel merge mode on Escape
  useEffect(() => {
    if (!mergingGroupId) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setMergingGroupId(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mergingGroupId])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-6 gap-4">
        <div className="flex items-center gap-3">
          <Tags className="h-5 w-5 text-primary" />
          <h1 className="text-2xl font-bold leading-none">{t('tags.title')}</h1>
          {groups.length > 0 && (
            <span className="inline-flex items-center h-6 px-2.5 rounded-full bg-muted text-xs font-medium text-muted-foreground">
              {filteredGroups.length}{searchQuery && ` / ${groups.length}`}
            </span>
          )}
        </div>
        {isAdmin && token && (
          <div className="flex items-center gap-3 shrink-0">
            {groups.length > 0 && (
              <div className="flex items-center gap-2">
                <Switch
                  id="show-similarities"
                  checked={showSimilarities}
                  onCheckedChange={setShowSimilarities}
                />
                <label htmlFor="show-similarities" className="text-xs text-muted-foreground cursor-pointer select-none flex items-center gap-1">
                  <Network className="h-3 w-3" />
                  Show Similarities
                </label>
              </div>
            )}
            {selectedTopic && (
              <div className="flex items-center gap-2">
                <Switch
                  id="auto-tag-groups"
                  checked={autoTagGroups}
                  onCheckedChange={handleAutoTagGroupsToggle}
                />
                <label htmlFor="auto-tag-groups" className="text-xs text-muted-foreground cursor-pointer select-none">
                  Auto Tag Groups
                </label>
              </div>
            )}
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
          </div>
        )}
      </div>

      <div className="max-w-3xl mx-auto w-full space-y-6">
      {/* ── Merge mode banner ── */}
      {mergingGroupId && (
        <div className="flex items-center justify-between rounded-lg border border-primary/40 bg-primary/5 px-4 py-2.5 text-sm">
          <span className="text-primary font-medium flex items-center gap-1.5">
            <GitMerge className="h-4 w-4" />
            Click another group to merge with <strong>{groups.find(g => g.id === mergingGroupId)?.display_name}</strong>
          </span>
          <button
            className="text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setMergingGroupId(null)}
          >
            Cancel (Esc)
          </button>
        </div>
      )}

      {/* ── Search ── */}
      {!isGuest && !loading && groups.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
          <input
            className="w-full rounded-lg border border-border bg-background pl-9 pr-9 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            placeholder="Search groups or tags..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setSearchQuery('')}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      )}

      {/* ── Paywall for guests ── */}
      {isGuest ? (
        <div className="relative">
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
          ) : filteredGroups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No groups or tags match &quot;{searchQuery}&quot;</p>
          ) : (
            <DndContext
              sensors={sensors}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <div className="relative space-y-4">
                {filteredGroups.map(group => {
                  const isSimilar = showSimilarities && isAdmin && group.similar_groups.length > 0
                  const pendingIncomingTagIds = new Set(
                    [...pendingMoves.values()]
                      .filter(m => m.toGroupId === group.id)
                      .map(m => m.tag.id)
                  )
                  const isMergeSource = mergingGroupId === group.id
                  const isMergeMode = !!mergingGroupId && !isMergeSource
                  return (
                    <div
                      key={group.id}
                      ref={el => { if (el) groupRefs.current.set(group.id, el) }}
                      className={isSimilar ? 'rounded-xl ring-2 ring-amber-400/60' : ''}
                    >
                      <TagGroupCard
                        group={group}
                        isAdmin={isAdmin}
                        token={token}
                        pendingIncomingTagIds={pendingIncomingTagIds}
                        isMergeMode={isMergeMode}
                        isMergeSource={isMergeSource}
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
                        onMergeRequested={handleMergeRequested}
                        onMergeTargetSelected={handleMergeTargetSelected}
                      />
                    </div>
                  )
                })}
                {showSimilarities && isAdmin && (
                  <SimilarityLines
                    groups={filteredGroups}
                    groupRefs={groupRefs}
                    onMergeRequested={handleMergeFromLine}
                  />
                )}
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
                {activeDragGroup && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-primary bg-card text-xs shadow-md cursor-grabbing">
                    <GitMerge className="h-3.5 w-3.5 text-primary" />
                    Merging: {activeDragGroup.display_name}
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
      </div>

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

      {mergeGroupPair && token && (
        <MergeGroupDialog
          groupA={mergeGroupPair[0]}
          groupB={mergeGroupPair[1]}
          token={token}
          onMerged={handleMerged}
          onClose={() => setMergeGroupPair(null)}
        />
      )}
    </div>
  )
}
