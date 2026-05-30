'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { useI18n, useGuestMode } from '@/lib/providers'
import { useTopic } from '@/lib/providers/topic-provider'
import dynamic from 'next/dynamic'
import { fetchAnalysesGraph, fetchAnalysesGraphGroup, type GraphFilters } from '@/lib/api/graph'
import { fetchArticleById } from '@/lib/api/articles'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ExternalLink, X, Globe, Clock } from 'lucide-react'
import { FilterBar } from '@/components/features/articles/filter-bar'

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

function applyArticleFilter(data: GraphData, filter: Set<string>): GraphData {
  const keptArticleIds = new Set(
    data.nodes
      .filter(n => n.type === 'article' && filter.has(n.articleId ?? ''))
      .map(n => n.id)
  )
  const keptTagIds = new Set(
    data.nodes
      .filter(n => {
        if (n.type !== 'tag') return false
        return data.edges.some(
          e => (e.source === n.id && keptArticleIds.has(e.target)) ||
               (e.target === n.id && keptArticleIds.has(e.source))
        )
      })
      .map(n => n.id)
  )
  const keptGroupIds = new Set(
    data.nodes
      .filter(n => {
        if (n.type !== 'group') return false
        return data.edges.some(
          e => (e.source === n.id && keptTagIds.has(e.target)) ||
               (e.target === n.id && keptTagIds.has(e.source))
        )
      })
      .map(n => n.id)
  )
  const allKept = new Set([...keptArticleIds, ...keptTagIds, ...keptGroupIds])
  return {
    nodes: data.nodes.filter(n => allKept.has(n.id)),
    edges: data.edges.filter(e => allKept.has(e.source) && allKept.has(e.target)),
  }
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

export function KnowledgeGraph({ articleIdFilter }: { articleIdFilter?: Set<string> }) {
  const { status } = useSession()
  const { t, locale } = useI18n()
  const { isGuestMode } = useGuestMode()
  const isPaywall = status === 'unauthenticated' && !isGuestMode
  const { selectedTopicId } = useTopic()

  const [graphFilters, setGraphFilters] = useState<Omit<GraphFilters, 'topic_id'>>({
    published_after: (() => {
      const d = new Date(); d.setDate(d.getDate() - 30); return d.toISOString().slice(0, 10)
    })(),
  })
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] })
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null)
  const [expandedGroupLabel, setExpandedGroupLabel] = useState('')
  const [expandedGroupColor, setExpandedGroupColor] = useState('#6b7280')
  const [groupData, setGroupData] = useState<GroupArticle[]>([])

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
    if (isPaywall) {
      setGraphData(GUEST_GRAPH)
      setGraphLoading(false)
      return
    }
    if (!selectedTopicId) return
    setGraphLoading(true)
    fetchAnalysesGraph({ topic_id: selectedTopicId, ...graphFilters }, locale)
      .then(data => setGraphData({ nodes: data.nodes, edges: data.edges }))
      .finally(() => setGraphLoading(false))
  }, [graphFilters, selectedTopicId, isPaywall, locale])

  // Clear article hover cache when locale changes (stale translations)
  useEffect(() => { articleCacheRef.current.clear() }, [locale])

  // Re-fetch group data when locale changes while a group is expanded
  useEffect(() => {
    if (!expandedGroup || isPaywall) return
    fetchAnalysesGraphGroup<GroupArticle>(expandedGroup, { ...graphFilters, topic_id: selectedTopicId ?? undefined }, locale)
      .then(setGroupData)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale, expandedGroup])

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

  const displayGraphData = useMemo(() => {
    if (articleIdFilter && articleIdFilter.size > 0) return applyArticleFilter(graphData, articleIdFilter)
    return graphData
  }, [graphData, articleIdFilter])

  const mergedGraphData = useMemo(() => ({
    nodes: displayGraphData.nodes,
    links: displayGraphData.edges,
  }), [displayGraphData])

  function handleNodeClick(node: any) {
    if (node.type === 'group') {
      if (expandedGroupRef.current === node.groupName) {
        setExpandedGroup(null)
        setGroupData([])
        setSelectedArticle(null)
      } else {
        setExpandedGroup(node.groupName)
        setExpandedGroupLabel(node.label)
        setExpandedGroupColor(node.color || '#6b7280')
        setSelectedArticle(null)

        fetchAnalysesGraphGroup<GroupArticle>(node.groupName, { ...graphFilters, topic_id: selectedTopicId ?? undefined }, locale)
          .then(setGroupData)
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
      fetchArticleById(articleId, locale)
        .then(data => { setDialogDetail(data); setDialogLoading(false) })
        .catch(() => setDialogLoading(false))
    }
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-14rem)]">
      {/* Graph — 60% */}
      <div className="w-[60%] flex flex-col gap-3">
        {!isPaywall && !isGuestMode && (
          <FilterBar
            sources={graphFilters.source ?? []}
            tags={graphFilters.tag ?? []}
            tagGroups={graphFilters.tag_group ?? []}
            publishedAfter={graphFilters.published_after ?? ''}
            publishedBefore={graphFilters.published_before ?? ''}
            scrapedAfter={graphFilters.scraped_after ?? ''}
            scrapedBefore={graphFilters.scraped_before ?? ''}
            activeFilterCount={
              (graphFilters.source?.length ? 1 : 0) +
              (graphFilters.tag?.length || graphFilters.tag_group?.length ? 1 : 0) +
              ((graphFilters.published_after || graphFilters.published_before) ? 1 : 0) +
              ((graphFilters.scraped_after || graphFilters.scraped_before) ? 1 : 0)
            }
            onApply={updates => setGraphFilters(prev => ({
              ...prev,
              source: updates.source,
              tag: updates.tag,
              tag_group: updates.tag_group,
              published_after: updates.published_after,
              published_before: updates.published_before,
              scraped_after: updates.scraped_after,
              scraped_before: updates.scraped_before,
            }))}
          />
        )}

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
                    fetchArticleById(node.id, locale)
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
                    {t('analysis.painPoints')}
                  </span>
                  <p className="text-xs text-foreground mt-0.5 leading-relaxed">
                    {selectedArticle.pain_points}
                  </p>
                </div>
              )}
              {selectedArticle.insights && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t('analysis.insights')}
                  </span>
                  <p className="text-xs text-foreground mt-0.5 leading-relaxed">
                    {selectedArticle.insights}
                  </p>
                </div>
              )}
              {selectedArticle.innovations && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t('analysis.innovations')}
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
                {t('graph.viewFullArticle')}
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
                  setSelectedArticle(null)
                }}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

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
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{t('analysis.painPoints')}</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.pain_points}</p>
                      </div>
                    )}
                    {a.insights && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{t('analysis.insights')}</span>
                        <p className="text-xs text-foreground mt-0.5 leading-relaxed">{a.insights}</p>
                      </div>
                    )}
                    {a.innovations && (
                      <div>
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{t('analysis.innovations')}</span>
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
            {t('graph.clickToExplore')}
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
                  {new Date(dialogDetail.published_at).toLocaleDateString(locale === 'zh-TW' ? 'zh-TW' : 'en-US', {
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
                  <ExternalLink className="h-3 w-3" />{t('graph.original')}
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
                      {t('analysis.painPoints')}
                    </h4>
                    <p className="text-sm text-foreground leading-relaxed">{dialogDetail.pain_points}</p>
                  </div>
                )}
                {dialogDetail.insights && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      {t('analysis.insights')}
                    </h4>
                    <p className="text-sm text-foreground leading-relaxed">{dialogDetail.insights}</p>
                  </div>
                )}
                {dialogDetail.innovations && (
                  <div>
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                      {t('analysis.innovations')}
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
