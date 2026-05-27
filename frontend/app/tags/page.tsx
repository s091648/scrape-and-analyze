'use client'
import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { Network, Plus, X, Lock, GitMerge, Tags, Search, GripVertical } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { TagModeSelector, type TagMode } from '@/components/features/tags/tag-mode-selector'
import { useTopic, useI18n } from '@/lib/providers'
import {
  fetchTagGroups, fetchTagGroup, fetchPendingSuggestions, createTagGroup, moveTag, batchMoveTags,
  reorderTagGroups,
  type TagGroupOut, type SuggestionOut, type TagGroupCreate, type TagOut,
} from '@/lib/api/tags'
import { TagGroupCard } from '@/components/features/tags/tag-group-card'
import { PendingSuggestions } from '@/components/features/tags/pending-suggestions'
import { PendingChangesPanel } from '@/components/features/tags/pending-changes-panel'
import { MergeGroupDialog } from '@/components/features/tags/merge-group-dialog'
import {
  DndContext, DragOverlay, MouseSensor, TouchSensor,
  useSensor, useSensors,
  type DragEndEvent, type DragOverEvent, type DragStartEvent,
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
  onLineClicked,
  isolatedPair,
}: {
  groups: TagGroupOut[]
  groupRefs: React.RefObject<Map<string, HTMLDivElement>>
  onMergeRequested: (groupAId: string, groupBId: string) => void
  onLineClicked: (groupAId: string, groupBId: string) => void
  isolatedPair: { a: string; b: string } | null
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
    const visibleGroupIds = new Set(groups.map(g => g.id))

    for (const group of groups) {
      for (const sim of group.similar_groups) {
        if (!group.id || !sim.id) continue
        if (!visibleGroupIds.has(sim.id)) continue
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
          const isIsolated = isolatedPair &&
            ((l.groupAId === isolatedPair.a && l.groupBId === isolatedPair.b) ||
             (l.groupAId === isolatedPair.b && l.groupBId === isolatedPair.a))
          const t = Math.min(1, Math.max(0, (l.score - 0.9) / 0.1))
          const baseOpacity = 0.15 + t * 0.85
          const opacity = isHovered || isIsolated ? 1 : baseOpacity
          const strokeWidth = isHovered || isIsolated ? 3 : 0.75 + t * 2.25
          const color = isIsolated ? 'rgb(99,102,241)' : 'rgb(251,191,36)'
          const d = `M ${l.x1} ${l.y1} H ${l.pivot} V ${l.y2} H ${l.x2}`

          return (
            <g
              key={l.key}
              opacity={opacity}
              style={{ pointerEvents: 'auto', cursor: 'pointer' }}
              onMouseEnter={() => setHoveredKey(l.key)}
              onMouseLeave={() => setHoveredKey(null)}
              onClick={() => onLineClicked(l.groupAId, l.groupBId)}
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
                      fill={isIsolated ? 'rgb(238,242,255)' : 'rgb(254,243,199)'}
                      stroke={isIsolated ? 'rgb(99,102,241)' : 'rgb(251,191,36)'} strokeWidth={0.75}
                    />
                    <text
                      x={l.pivot} y={midY}
                      textAnchor="middle" dominantBaseline="middle"
                      fontSize={9} fontWeight="600"
                      fill={isIsolated ? 'rgb(67,56,202)' : 'rgb(146,64,14)'}
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
  const { selectedTopic, refresh: refreshTopics } = useTopic()
  const { t } = useI18n()

  const isGuest = status === 'unauthenticated'

  const [groups, setGroups] = useState<TagGroupOut[]>([])
  const [suggestions, setSuggestions] = useState<SuggestionOut[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddGroup, setShowAddGroup] = useState(false)

  const [tagMode, setTagMode] = useState<TagMode>(
    (selectedTopic?.tag_mode ?? 'unsupervised') as TagMode
  )

  const [showSimilarities, setShowSimilarities] = useState(false)
  const similaritiesInitialized = useRef(false)
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

  // ── Isolated line state ──
  const [isolatedPair, setIsolatedPair] = useState<{ a: string; b: string } | null>(null)

  const displayedGroups = useMemo(() => {
    if (!isolatedPair) return filteredGroups
    return filteredGroups.filter(g => g.id === isolatedPair.a || g.id === isolatedPair.b)
  }, [filteredGroups, isolatedPair])

  useEffect(() => {
    setTagMode((selectedTopic?.tag_mode ?? 'unsupervised') as TagMode)
  }, [selectedTopic?.id])

  // Default similarities on for admins (fires once when session confirms admin)
  useEffect(() => {
    if (isAdmin && !similaritiesInitialized.current) {
      setShowSimilarities(true)
      similaritiesInitialized.current = true
    }
  }, [isAdmin])

  async function handleTagModeChange(mode: TagMode) {
    if (!selectedTopic) return
    const prev = tagMode
    setTagMode(mode)
    try {
      const { updateTopic } = await import('@/lib/api/topics')
      await updateTopic(selectedTopic.id, { tag_mode: mode }, token)
      refreshTopics()
    } catch {
      setTagMode(prev)
    }
  }

  interface PendingMove {
    tag: TagOut
    fromGroupId: string
    toGroupId: string
    toGroupName: string
  }

  const [pendingMoves, setPendingMoves] = useState<Map<string, PendingMove>>(new Map())
  const [overZoneId, setOverZoneId] = useState<string | null>(null)
  const [activeDragTag, setActiveDragTag] = useState<TagOut | null>(null)
  const [activeDragGroup, setActiveDragGroup] = useState<TagGroupOut | null>(null)
  const [isGroupDragActive, setIsGroupDragActive] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [selectedTagIds, setSelectedTagIds] = useState<Set<string>>(new Set())
  const activeDragTagIdsRef = useRef<Set<string>>(new Set())
  const [activeDragCount, setActiveDragCount] = useState(0)
  const dragStartGroupsRef = useRef<TagGroupOut[] | null>(null)
  const currentGroupsRef = useRef<TagGroupOut[]>(groups)
  useEffect(() => { currentGroupsRef.current = groups }, [groups])

  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
  )

  function handleDragStart({ active }: DragStartEvent) {
    if (active.data.current?.type === 'group-sort') {
      setActiveDragGroup(active.data.current.group ?? null)
      setIsGroupDragActive(true)
      dragStartGroupsRef.current = [...groups]
      return
    }
    const tag: TagOut = active.data.current?.tag
    setActiveDragTag(tag ?? null)
    // If dragging a selected tag, move the whole selection; otherwise just this tag
    const tagIds = selectedTagIds.has(tag.id)
      ? new Set(selectedTagIds)
      : new Set([tag.id])
    if (!selectedTagIds.has(tag.id)) setSelectedTagIds(new Set())
    activeDragTagIdsRef.current = tagIds
    setActiveDragCount(tagIds.size)
  }

  function handleDragOver({ active, over }: DragOverEvent) {
    if (active.data.current?.type === 'group-sort') {
      setOverZoneId(over ? String(over.id) : null)
    }
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveDragTag(null)
    setActiveDragGroup(null)
    setIsGroupDragActive(false)
    setOverZoneId(null)
    const tagIdsToMove = activeDragTagIdsRef.current
    activeDragTagIdsRef.current = new Set()
    setActiveDragCount(0)

    // Group sort / merge
    if (active.data.current?.type === 'group-sort') {
      dragStartGroupsRef.current = null
      if (!over) return

      const overId = String(over.id)
      const draggedGroupId = active.data.current.group.id

      if (overId.startsWith('merge:')) {
        const targetGroupId = overId.slice('merge:'.length)
        if (targetGroupId !== draggedGroupId) {
          handleMergeFromLine(draggedGroupId, targetGroupId)
        }
        return
      }

      let targetGroupId: string | null = null
      let insertBefore = false

      if (overId.startsWith('sort-above:')) {
        targetGroupId = overId.slice('sort-above:'.length)
        insertBefore = true
      } else if (overId.startsWith('sort-below:')) {
        targetGroupId = overId.slice('sort-below:'.length)
        insertBefore = false
      }

      if (!targetGroupId || targetGroupId === draggedGroupId) return

      setGroups(prev => {
        const dragged = prev.find(g => g.id === draggedGroupId)
        if (!dragged) return prev
        const without = prev.filter(g => g.id !== draggedGroupId)
        const targetIdx = without.findIndex(g => g.id === targetGroupId)
        if (targetIdx === -1) return prev
        const insertAt = insertBefore ? targetIdx : targetIdx + 1
        const newOrder = [...without.slice(0, insertAt), dragged, ...without.slice(insertAt)]
        if (token) {
          reorderTagGroups(
            newOrder.map((g, i) => ({ id: g.id, sort_order: i })),
            token,
          ).catch(() => {})
        }
        return newOrder
      })
      return
    }

    if (!over) return

    const toGroupId = String(over.id)
    const toGroup = groups.find(g => g.id === toGroupId)
    if (!toGroup) return

    type MoveItem = { tag: TagOut; fromGroupId: string; originalFromGroupId: string }
    const moves: MoveItem[] = []
    for (const tagId of tagIdsToMove) {
      const fromGroup = groups.find(g => g.tags.some(t => t.id === tagId))
      if (!fromGroup || fromGroup.id === toGroupId) continue
      const tag = fromGroup.tags.find(t => t.id === tagId)!
      const existingPending = pendingMoves.get(tagId)
      const originalFromGroupId = existingPending?.fromGroupId ?? fromGroup.id
      moves.push({ tag, fromGroupId: fromGroup.id, originalFromGroupId })
    }

    if (moves.length === 0) return

    setGroups(prev => {
      let next = prev
      for (const { tag, fromGroupId, originalFromGroupId } of moves) {
        if (toGroupId === originalFromGroupId) {
          next = next.map(g =>
            g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
            g.id === originalFromGroupId ? { ...g, tags: [...g.tags, tag] } : g
          )
        } else {
          next = next.map(g =>
            g.id === fromGroupId ? { ...g, tags: g.tags.filter(t => t.id !== tag.id) } :
            g.id === toGroupId ? { ...g, tags: [...g.tags, tag] } : g
          )
        }
      }
      return next
    })

    setPendingMoves(prev => {
      const next = new Map(prev)
      for (const { tag, originalFromGroupId } of moves) {
        if (toGroupId === originalFromGroupId) {
          next.delete(tag.id)
        } else {
          next.set(tag.id, { tag, fromGroupId: originalFromGroupId, toGroupId, toGroupName: toGroup.name })
        }
      }
      return next
    })

    setSelectedTagIds(new Set())
  }

  async function handleConfirm() {
    if (!token || pendingMoves.size === 0) return
    setConfirming(true)
    const moves = [...pendingMoves.values()]

    if (moves.length === 1) {
      const m = moves[0]
      try {
        await moveTag(m.tag.id, m.toGroupId, token)
        setPendingMoves(new Map())
      } catch {
        // leave in pending state for retry
      }
    } else {
      try {
        const result = await batchMoveTags(
          moves.map(m => ({ tag_id: m.tag.id, tag_group_id: m.toGroupId })),
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

  // ── Line click to isolate ──
  function handleLineClicked(groupAId: string, groupBId: string) {
    setIsolatedPair({ a: groupAId, b: groupBId })
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

  async function handleMerged(result: TagGroupOut) {
    if (!mergeGroupPair) return
    const [groupA, groupB] = mergeGroupPair
    setMergeGroupPair(null)

    try {
      const freshGroups = await fetchTagGroups(selectedTopic?.id, isAdmin && showSimilarities)
      setGroups(freshGroups)
    } catch {
      // Fall back to local optimistic update
      let fresh = result
      try { fresh = await fetchTagGroup(result.id) } catch {}
      setGroups(prev => {
        const idxA = prev.findIndex(g => g.id === groupA.id)
        const withoutBoth = prev.filter(g => g.id !== groupA.id && g.id !== groupB.id)
        const insertAt = idxA === -1 ? withoutBoth.length : Math.min(idxA, withoutBoth.length)
        return [...withoutBoth.slice(0, insertAt), fresh, ...withoutBoth.slice(insertAt)]
      })
    }
  }

  useEffect(() => {
    if (isGuest) { setLoading(false); return }
    setLoading(true)
    const topicId = selectedTopic?.id
    let cancelled = false
    Promise.all([
      fetchTagGroups(topicId, isAdmin && showSimilarities),
      isAdmin && token ? fetchPendingSuggestions(token) : Promise.resolve([]),
    ])
      .then(([g, s]) => { if (!cancelled) { setGroups(g); setSuggestions(s) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
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

  // Cancel isolated line on Escape
  useEffect(() => {
    if (!isolatedPair) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setIsolatedPair(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isolatedPair])

  // Clear tag selection on Escape
  useEffect(() => {
    if (selectedTagIds.size === 0) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setSelectedTagIds(new Set())
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedTagIds.size])

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
                <span className="text-xs text-muted-foreground">{t('tags.tagMode')}</span>
                <TagModeSelector value={tagMode} onChange={handleTagModeChange} />
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
      {/* ── Isolated line banner ── */}
      {isolatedPair && (() => {
        const groupA = groups.find(g => g.id === isolatedPair.a)
        const groupB = groups.find(g => g.id === isolatedPair.b)
        return (
          <div className="flex items-center justify-between rounded-lg border border-indigo-400/40 bg-indigo-500/5 px-4 py-2.5 text-sm">
            <span className="text-indigo-500 font-medium flex items-center gap-1.5">
              <Network className="h-4 w-4" />
              Viewing similarity: <strong>{groupA?.display_name}</strong> ↔ <strong>{groupB?.display_name}</strong>
            </span>
            <button
              className="text-xs text-muted-foreground hover:text-foreground"
              onClick={() => setIsolatedPair(null)}
            >
              Show All (Esc)
            </button>
          </div>
        )
      })()}

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

      {/* ── Multi-select banner ── */}
      {selectedTagIds.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-primary/40 bg-primary/5 px-4 py-2.5 text-sm">
          <span className="text-primary font-medium flex items-center gap-1.5">
            <Tags className="h-4 w-4" />
            {selectedTagIds.size} tag{selectedTagIds.size !== 1 ? 's' : ''} selected — drag any selected tag to move all
          </span>
          <button
            className="text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setSelectedTagIds(new Set())}
          >
            Clear (Esc)
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
              onDragOver={handleDragOver}
              onDragEnd={handleDragEnd}
            >
              <div className="relative space-y-4">
                {displayedGroups.map((group, idx) => {
                  const isSimilar = showSimilarities && isAdmin && group.similar_groups.length > 0
                  const pendingIncomingTagIds = new Set(
                    [...pendingMoves.values()]
                      .filter(m => m.toGroupId === group.id)
                      .map(m => m.tag.id)
                  )
                  const isMergeSource = mergingGroupId === group.id
                  const isMergeMode = !!mergingGroupId && !isMergeSource
                  const isDraggedCard = activeDragGroup?.id === group.id
                  const prevGroupId = displayedGroups[idx - 1]?.id
                  const nextGroupId = displayedGroups[idx + 1]?.id
                  const oz = overZoneId ?? ''
                  const showTopInsert = !isDraggedCard && isGroupDragActive && (
                    oz === `sort-above:${group.id}` ||
                    (prevGroupId != null && oz === `sort-below:${prevGroupId}`)
                  )
                  const showBottomInsert = !isDraggedCard && isGroupDragActive && (
                    oz === `sort-below:${group.id}` ||
                    (nextGroupId != null && oz === `sort-above:${nextGroupId}`)
                  )
                  return (
                    <div
                      key={group.id ?? '__ungrouped__'}
                      ref={el => { if (el && group.id) groupRefs.current.set(group.id, el); else if (group.id) groupRefs.current.delete(group.id) }}
                      className={isSimilar ? 'rounded-xl ring-2 ring-amber-400/60' : ''}
                    >
                      <TagGroupCard
                        group={group}
                        isAdmin={isAdmin}
                        token={token}
                        pendingIncomingTagIds={pendingIncomingTagIds}
                        isMergeMode={isMergeMode}
                        isMergeSource={isMergeSource}
                        isGroupDragActive={isGroupDragActive}
                        showTopInsert={showTopInsert}
                        showBottomInsert={showBottomInsert}
                        selectedTagIds={selectedTagIds}
                        onTagSelectionToggle={tagId => setSelectedTagIds(prev => {
                          const next = new Set(prev)
                          if (next.has(tagId)) next.delete(tagId)
                          else next.add(tagId)
                          return next
                        })}
                        onDeleted={groupId => setGroups(prev => {
                          const deleted = prev.find(g => g.id === groupId)
                          const tagsToRehome = deleted?.tags ?? []
                          const without = prev.filter(g => g.id !== groupId)
                          if (tagsToRehome.length === 0) return without
                          const ungrouped = without.find(g => g.id === null)
                          if (ungrouped) {
                            return without.map(g => g.id === null
                              ? { ...g, tags: [...ungrouped.tags, ...tagsToRehome] }
                              : g
                            )
                          }
                          return [...without, {
                            id: null, name: 'ungrouped', display_name: 'Ungrouped',
                            description: null, color_hex: null, topic_id: deleted?.topic_id ?? null,
                            tags: tagsToRehome, similar_groups: [],
                          }]
                        })}
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
                    groups={displayedGroups.filter(g => g.id !== null)}
                    groupRefs={groupRefs}
                    onMergeRequested={handleMergeFromLine}
                    onLineClicked={handleLineClicked}
                    isolatedPair={isolatedPair}
                  />
                )}
              </div>
              <DragOverlay>
                {activeDragTag && (
                  <div className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-primary bg-card text-xs shadow-md cursor-grabbing">
                    {activeDragCount > 1 ? (
                      <span>{activeDragCount} tags</span>
                    ) : (
                      <>
                        {activeDragTag.name}
                        <span className="text-muted-foreground tabular-nums">
                          ({activeDragTag.article_count})
                        </span>
                      </>
                    )}
                  </div>
                )}
                {activeDragGroup && (
                  <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-card text-xs shadow-md cursor-grabbing opacity-80">
                    <GripVertical className="h-3.5 w-3.5 text-muted-foreground" />
                    {activeDragGroup.display_name}
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
