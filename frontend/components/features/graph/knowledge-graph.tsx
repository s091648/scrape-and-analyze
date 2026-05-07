'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { useTopic } from '@/lib/providers/topic-provider'
import dynamic from 'next/dynamic'
import { apiFetch } from '@/lib/api/client'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ExternalLink, X, Globe, Clock } from 'lucide-react'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), { ssr: false })

const CHARGE_STRENGTH = -300   // repulsion between nodes (more negative = more spread)
const LINK_DISTANCE  = 100     // preferred edge length

interface GraphNode {
  id: string
  type: 'group' | 'article' | 'tag'
  label: string
  color?: string
  groupName?: string
  articleCount?: number
  articleId?: string
}
interface GraphEdge { source: string; target: string }
interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

// Fake graph shown to guests — API is never called
const GUEST_GRAPH: GraphData = {
  nodes: [
    { id: 'g1', type: 'group', label: 'Lorem Ipsum',      color: '#6366f1', articleCount: 8 },
    { id: 'g2', type: 'group', label: 'Dolor Sit Amet',   color: '#22c55e', articleCount: 5 },
    { id: 'g3', type: 'group', label: 'Consectetur',      color: '#f59e0b', articleCount: 6 },
    { id: 'g4', type: 'group', label: 'Adipiscing Elit',  color: '#ec4899', articleCount: 4 },
    { id: 't1', type: 'tag',   label: 'lorem',       color: '#94a3b8', groupName: 'g1' },
    { id: 't2', type: 'tag',   label: 'ipsum',       color: '#94a3b8', groupName: 'g1' },
    { id: 't3', type: 'tag',   label: 'dolor',       color: '#94a3b8', groupName: 'g2' },
    { id: 't4', type: 'tag',   label: 'consectetur', color: '#94a3b8', groupName: 'g3' },
    { id: 't5', type: 'tag',   label: 'adipiscing',  color: '#94a3b8', groupName: 'g4' },
    { id: 't6', type: 'tag',   label: 'elit',        color: '#94a3b8', groupName: 'g4' },
  ],
  edges: [
    { source: 'g1', target: 't1' }, { source: 'g1', target: 't2' },
    { source: 'g2', target: 't3' }, { source: 'g3', target: 't4' },
    { source: 'g4', target: 't5' }, { source: 'g4', target: 't6' },
    { source: 'g1', target: 'g2' }, { source: 'g2', target: 'g3' },
    { source: 'g3', target: 'g4' }, { source: 'g1', target: 'g3' },
  ],
}

interface GroupArticle {
  groupName: string
  displayName: string
  tags: string[]
  articleId: string
  title: string
  source: string
  url: string
  published_at: string | null
  excerpt: string
  pain_points: string | null
  insights: string | null
  innovations: string | null
}

export function KnowledgeGraph() {
  const [days, setDays] = useState(30)
  const { status } = useSession()
  const isGuest = status === 'unauthenticated'
  const { selectedTopicId } = useTopic()
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] })
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null)
  const [expandedGroupLabel, setExpandedGroupLabel] = useState('')
  const [expandedGroupColor, setExpandedGroupColor] = useState('#6b7280')
  const [groupData, setGroupData] = useState<GroupArticle[]>([])

  // Overlay state (tag nodes + edges injected on group expand)
  const [overlayNodes, setOverlayNodes] = useState<GraphNode[]>([])
  const [overlayEdges, setOverlayEdges] = useState<GraphEdge[]>([])

  // Article selection state
  const [selectedArticle, setSelectedArticle] = useState<GroupArticle | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogDetail, setDialogDetail] = useState<any>(null)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [graphLoading, setGraphLoading] = useState(true)

  const graphContainerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<any>(null)
  const forcesConfigured = useRef(false)
  const hoveredNodeIdRef = useRef<string | null>(null)
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const articleCacheRef = useRef<Map<string, GroupArticle>>(new Map())
  const [graphDims, setGraphDims] = useState({ width: 600, height: 500 })

  // Stable refs (used inside canvas callbacks)
  const groupDataRef = useRef<GroupArticle[]>([])
  const expandedGroupRef = useRef<string | null>(null)
  const selectedArticleRef = useRef<GroupArticle | null>(null)
  useEffect(() => { groupDataRef.current = groupData }, [groupData])
  useEffect(() => { expandedGroupRef.current = expandedGroup }, [expandedGroup])
  useEffect(() => { selectedArticleRef.current = selectedArticle }, [selectedArticle])

  useEffect(() => {
    // Guests see fake data — API is never called (prevents data leakage via devtools)
    if (isGuest) {
      setGraphData(GUEST_GRAPH)
      setGraphLoading(false)
      return
    }
    if (!selectedTopicId) return
    setGraphLoading(true)
    apiFetch(`/analyses/graph?days=${days}&topic_id=${selectedTopicId}`)
      .then(r => r.json())
      .then(data => setGraphData({ nodes: data.nodes, edges: data.edges }))
      .finally(() => setGraphLoading(false))
  }, [days, selectedTopicId, isGuest])

  useEffect(() => {
    const el = graphContainerRef.current
    if (!el) return
    const obs = new ResizeObserver(entries => {
      const e = entries[0]
      if (e) setGraphDims({ width: e.contentRect.width, height: e.contentRect.height })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Merged graph data: base nodes/edges + tag overlay
  const mergedGraphData = useMemo(() => ({
    nodes: [...graphData.nodes, ...overlayNodes],
    links: [...graphData.edges, ...overlayEdges],
  }), [graphData, overlayNodes, overlayEdges])

  function handleNodeClick(node: any) {
    if (node.type === 'group') {
      if (expandedGroupRef.current === node.groupName) {
        // Collapse
        setExpandedGroup(null)
        setGroupData([])
        setOverlayNodes([])
        setOverlayEdges([])
        setSelectedArticle(null)
      } else {
        setExpandedGroup(node.groupName)
        setExpandedGroupLabel(node.label)
        setExpandedGroupColor(node.color || '#6b7280')
        setOverlayNodes([])
        setOverlayEdges([])
        setSelectedArticle(null)

        apiFetch(`/analyses/graph/group/${encodeURIComponent(node.groupName)}`)
          .then(r => r.json())
          .then((data: GroupArticle[]) => {
            setGroupData(data)

            // Build tag overlay nodes and edges
            const uniqueTags = [...new Set(data.flatMap(a => a.tags))]

            const tagNodes: GraphNode[] = uniqueTags.map(tag => ({
              id: `tag::${node.groupName}::${tag}`,
              type: 'tag' as const,
              label: tag,
              color: node.color || '#6b7280',
              groupName: node.groupName,
            }))

            const tagEdges: GraphEdge[] = [
              // group → tag
              ...uniqueTags.map(tag => ({
                source: node.id,
                target: `tag::${node.groupName}::${tag}`,
              })),
              // tag → article
              ...data.flatMap(article =>
                article.tags.map(tag => ({
                  source: `tag::${node.groupName}::${tag}`,
                  target: article.articleId,
                }))
              ),
            ]

            setOverlayNodes(tagNodes)
            setOverlayEdges(tagEdges)
          })
      }
    } else if (node.type === 'article') {
      const article = groupDataRef.current.find(a => a.articleId === node.id)
      if (article) {
        setSelectedArticle(article)
      } else {
        // Group not expanded — open full dialog directly
        openArticleDialog(node.id)
      }
    }
  }

  function openArticleDialog(articleId: string) {
    setDialogOpen(true)
    if (!dialogDetail || dialogDetail.id !== articleId) {
      setDialogLoading(true)
      setDialogDetail(null)
      apiFetch(`/articles/${articleId}`)
        .then(r => r.json())
        .then(data => { setDialogDetail(data); setDialogLoading(false) })
        .catch(() => setDialogLoading(false))
    }
  }

  // Aggregate unique tags across all articles in the selected group
  const aggregateTags = useMemo(() =>
    [...new Set(groupData.flatMap(a => a.tags))],
    [groupData]
  )

  return (
    <div className="flex gap-4 h-[calc(100vh-14rem)]">
      {/* Graph — 60% */}
      <div className="w-[60%] flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Time window:</label>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="text-sm border border-border rounded px-2 py-1 bg-background"
          >
            {[7, 30, 90, 180].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
        </div>

        <div
          ref={graphContainerRef}
          className="flex-1 min-h-0 relative"
        >
          {graphLoading ? (
            <Skeleton className="absolute inset-0 rounded-lg" />
          ) : (
            <ForceGraph
              ref={graphRef}
              graphData={mergedGraphData}
              width={graphDims.width}
              height={graphDims.height}
              nodeRelSize={6}
              onEngineStop={() => {
                // Configure d3 forces once after first cooldown, then reheat
                if (forcesConfigured.current || !graphRef.current) return
                forcesConfigured.current = true
                graphRef.current.d3Force('charge')?.strength(CHARGE_STRENGTH)
                graphRef.current.d3Force('link')?.distance(LINK_DISTANCE)
                graphRef.current.d3ReheatSimulation()
              }}
              onNodeClick={handleNodeClick}
              onNodeHover={(node: any) => {
                if (node?.type === 'article') {
                  hoveredNodeIdRef.current = node.id

                  // If the group is already expanded and has this article's data, use it directly
                  const groupArticle = groupDataRef.current.find(a => a.articleId === node.id)
                  if (groupArticle) {
                    setSelectedArticle(groupArticle)
                    return
                  }

                  // Check cache first
                  const cached = articleCacheRef.current.get(node.id)
                  if (cached) {
                    setSelectedArticle(cached)
                    return
                  }

                  // Debounce fetch so rapid mouse movement doesn't spam requests
                  if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
                  hoverTimeoutRef.current = setTimeout(() => {
                    if (hoveredNodeIdRef.current !== node.id) return
                    apiFetch(`/articles/${node.id}`)
                      .then(r => r.json())
                      .then(data => {
                        if (hoveredNodeIdRef.current !== node.id) return
                        const art: GroupArticle = {
                          articleId: data.id,
                          title: data.title,
                          pain_points: data.pain_points,
                          insights: data.insights,
                          innovations: data.innovations,
                          url: data.url || '',
                          tags: [],
                          groupName: '',
                          displayName: '',
                          source: data.source || '',
                          published_at: data.published_at,
                          excerpt: (data.content || '').slice(0, 200),
                        }
                        articleCacheRef.current.set(node.id, art)
                        setSelectedArticle(art)
                      })
                      .catch(() => {})
                  }, 250)
                } else {
                  hoveredNodeIdRef.current = null
                  if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current)
                }
              }}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const isGroup = node.type === 'group'
                const isExpanded = isGroup && expandedGroupRef.current === node.groupName

                if (isExpanded) {
                  // --- Expanded group: dashed outline + label only ---
                  const outerRadius = 20
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, outerRadius, 0, 2 * Math.PI)
                  ctx.setLineDash([5, 3])
                  ctx.strokeStyle = node.color || '#6b7280'
                  ctx.lineWidth = 2 / globalScale
                  ctx.stroke()
                  ctx.setLineDash([])

                  const titleFontSize = Math.max(11 / globalScale, 3)
                  ctx.font = `bold ${titleFontSize}px sans-serif`
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'bottom'
                  ctx.fillText(node.label, node.x, node.y - outerRadius - 4 / globalScale)

                } else if (isGroup) {
                  // --- Collapsed group node ---
                  const radius = 12
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.fill()

                  // Article count badge (larger font)
                  if (node.articleCount) {
                    const badgeFontSize = Math.max(14 / globalScale, 4)
                    ctx.font = `bold ${badgeFontSize}px sans-serif`
                    ctx.fillStyle = 'white'
                    ctx.textAlign = 'center'
                    ctx.textBaseline = 'middle'
                    ctx.fillText(String(node.articleCount), node.x, node.y)
                  }

                  // Label below
                  const label: string = node.label || node.id
                  const truncated = label.length > 22 ? label.slice(0, 20) + '…' : label
                  const fontSize = Math.max(10 / globalScale, 2)
                  ctx.font = `bold ${fontSize}px sans-serif`
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'top'
                  ctx.fillText(truncated, node.x, node.y + radius + 2)

                } else if (node.type === 'tag') {
                  // --- Tag node ---
                  const radius = 5
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.globalAlpha = 0.8
                  ctx.fill()
                  ctx.globalAlpha = 1.0

                  const tagFontSize = Math.max(9 / globalScale, 2)
                  ctx.font = `${tagFontSize}px sans-serif`
                  ctx.fillStyle = '#374151'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'top'
                  const truncTag = (node.label || '').length > 18
                    ? (node.label || '').slice(0, 16) + '…'
                    : (node.label || '')
                  ctx.fillText(truncTag, node.x, node.y + radius + 2)

                } else {
                  // --- Article node (small dot, title on hover) ---
                  const radius = 4
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                  ctx.fillStyle = '#10b981'
                  ctx.fill()

                  if (node.id === hoveredNodeIdRef.current) {
                    const label: string = node.label || ''
                    const truncated = label.length > 32 ? label.slice(0, 30) + '…' : label
                    const fontSize = Math.max(9 / globalScale, 2)
                    ctx.font = `${fontSize}px sans-serif`
                    ctx.fillStyle = '#111827'
                    ctx.textAlign = 'center'
                    ctx.textBaseline = 'top'
                    ctx.fillText(truncated, node.x, node.y + radius + 3)
                  }
                }
              }}
            />
          )}
        </div>
      </div>

      {/* Right panel — 40% */}
      <div className="w-[40%] flex flex-col min-h-0">
        {selectedArticle ? (
          /* Article detail view */
          <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
            <div className="flex items-start justify-between px-4 py-3 border-b border-border shrink-0">
              <h3 className="text-sm font-semibold text-foreground leading-snug pr-2">
                {selectedArticle.title}
              </h3>
              <button
                className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setSelectedArticle(null)}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
              {selectedArticle.pain_points && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Pain Points
                  </span>
                  <p className="text-xs text-foreground mt-0.5 leading-relaxed">
                    {selectedArticle.pain_points}
                  </p>
                </div>
              )}
              {selectedArticle.insights && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Insights
                  </span>
                  <p className="text-xs text-foreground mt-0.5 leading-relaxed">
                    {selectedArticle.insights}
                  </p>
                </div>
              )}
              {selectedArticle.innovations && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Innovations
                  </span>
                  <p className="text-xs text-foreground mt-0.5 leading-relaxed">
                    {selectedArticle.innovations}
                  </p>
                </div>
              )}
            </div>
            <div className="px-4 py-3 border-t border-border shrink-0">
              <button
                className="w-full text-xs font-medium text-center py-2 px-3 rounded-lg border border-border hover:bg-muted/40 transition-colors"
                onClick={() => openArticleDialog(selectedArticle.articleId)}
              >
                View Full Article
              </button>
            </div>
          </div>
        ) : expandedGroup ? (
          /* Group detail view */
          <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
            {/* Panel header */}
            <div
              className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0"
              style={{ borderLeftColor: expandedGroupColor, borderLeftWidth: 3 }}
            >
              <h3 className="text-sm font-semibold text-foreground">{expandedGroupLabel}</h3>
              <button
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => {
                  setExpandedGroup(null)
                  setGroupData([])
                  setOverlayNodes([])
                  setOverlayEdges([])
                  setSelectedArticle(null)
                }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Tag badges */}
            {aggregateTags.length > 0 && (
              <div className="px-4 py-3 border-b border-border shrink-0 flex flex-wrap gap-1.5">
                {aggregateTags.map(tag => (
                  <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                ))}
              </div>
            )}

            {/* Article list */}
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ul className="p-4 space-y-4">
                {groupData.map(a => (
                  <li key={a.articleId} className="space-y-2 pb-4 border-b border-border last:border-0 last:pb-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium leading-snug text-foreground">{a.title}</span>
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </div>
                    {a.excerpt && (
                      <p className="text-xs text-muted-foreground leading-relaxed">{a.excerpt}</p>
                    )}
                    {a.pain_points && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Pain Points</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.pain_points}</p>
                      </div>
                    )}
                    {a.insights && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Insights</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.insights}</p>
                      </div>
                    )}
                    {a.innovations && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Innovations</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.innovations}</p>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center border border-dashed border-border rounded-xl text-sm text-muted-foreground">
            Click a group node to explore
          </div>
        )}
      </div>

      {/* View Full Article dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col gap-0 p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
            <DialogTitle className="text-lg leading-snug pr-6">
              {dialogDetail?.title ?? selectedArticle?.title ?? ''}
            </DialogTitle>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              {dialogDetail?.source && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Globe className="h-3 w-3" />{dialogDetail.source}
                </span>
              )}
              {dialogDetail?.published_at && (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {new Date(dialogDetail.published_at).toLocaleDateString('en-US', {
                    month: 'short', day: 'numeric', year: 'numeric'
                  })}
                </span>
              )}
              {(dialogDetail?.url || selectedArticle?.url) && (
                <a
                  href={dialogDetail?.url ?? selectedArticle?.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <ExternalLink className="h-3 w-3" />Original
                </a>
              )}
            </div>
          </DialogHeader>
          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">
            {dialogLoading ? (
              <div className="space-y-3 py-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
                <Skeleton className="h-4 w-3/5" />
              </div>
            ) : dialogDetail ? (
              <div className="space-y-6">
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                  {dialogDetail.content}
                </p>
                {dialogDetail.pain_points && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Pain Points
                    </h4>
                    <p className="text-sm text-foreground leading-relaxed">{dialogDetail.pain_points}</p>
                  </div>
                )}
                {dialogDetail.insights && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Insights
                    </h4>
                    <p className="text-sm text-foreground leading-relaxed">{dialogDetail.insights}</p>
                  </div>
                )}
                {dialogDetail.innovations && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      Innovations
                    </h4>
                    <p className="text-sm text-foreground leading-relaxed">{dialogDetail.innovations}</p>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
