'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
import dynamic from 'next/dynamic'
import { apiFetch } from '@/lib/api-fetch'
import { Badge } from '@/components/ui/badge'
import { ExternalLink, X } from 'lucide-react'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), { ssr: false })

interface GraphNode {
  id: string
  type: 'group' | 'article'
  label: string
  color?: string
  groupName?: string
  articleCount?: number
  articleId?: string
}
interface GraphEdge { source: string; target: string }
interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

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
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] })
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null)
  const [expandedGroupLabel, setExpandedGroupLabel] = useState('')
  const [expandedGroupColor, setExpandedGroupColor] = useState('#6b7280')
  const [groupData, setGroupData] = useState<GroupArticle[]>([])

  const graphContainerRef = useRef<HTMLDivElement>(null)
  const [graphDims, setGraphDims] = useState({ width: 600, height: 500 })

  // Stable reference for the expanded group data (used inside canvas callback)
  const groupDataRef = useRef<GroupArticle[]>([])
  const expandedGroupRef = useRef<string | null>(null)
  useEffect(() => { groupDataRef.current = groupData }, [groupData])
  useEffect(() => { expandedGroupRef.current = expandedGroup }, [expandedGroup])

  useEffect(() => {
    apiFetch(`/analyses/graph?days=${days}`)
      .then(r => r.json())
      .then(data => setGraphData({ nodes: data.nodes, edges: data.edges }))
  }, [days])

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

  function handleNodeClick(node: any) {
    if (node.type === 'group') {
      if (expandedGroupRef.current === node.groupName) {
        setExpandedGroup(null)
        setGroupData([])
      } else {
        setExpandedGroup(node.groupName)
        setExpandedGroupLabel(node.label)
        setExpandedGroupColor(node.color || '#6b7280')
        apiFetch(`/analyses/graph/group/${encodeURIComponent(node.groupName)}`)
          .then(r => r.json())
          .then(setGroupData)
      }
    } else {
      setExpandedGroup(null)
      setGroupData([])
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
          className="flex-1 border border-border rounded-xl overflow-hidden bg-muted/10"
        >
          <ForceGraph
            graphData={{ nodes: graphData.nodes, links: graphData.edges }}
            width={graphDims.width}
            height={graphDims.height}
            nodeRelSize={6}
            onNodeClick={handleNodeClick}
            nodeCanvasObjectMode={() => 'replace'}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const isGroup = node.type === 'group'
              const isExpanded = isGroup && expandedGroupRef.current === node.groupName

              if (isExpanded) {
                // --- Expanded group: dashed outline + inner tag nodes ---
                const outerRadius = 52
                ctx.beginPath()
                ctx.arc(node.x, node.y, outerRadius, 0, 2 * Math.PI)
                ctx.setLineDash([5, 3])
                ctx.strokeStyle = node.color || '#6b7280'
                ctx.lineWidth = 2 / globalScale
                ctx.stroke()
                ctx.setLineDash([])

                // Group label above the circle
                const titleFontSize = Math.max(11 / globalScale, 3)
                ctx.font = `bold ${titleFontSize}px sans-serif`
                ctx.fillStyle = node.color || '#6b7280'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'bottom'
                ctx.fillText(node.label, node.x, node.y - outerRadius - 4 / globalScale)

                // Collect unique tags for this group from the ref (stable, no re-render needed)
                const allTags = [...new Set(
                  groupDataRef.current.flatMap(a => a.tags)
                )].slice(0, 8)

                allTags.forEach((tag, i) => {
                  const angle = (i / Math.max(allTags.length, 1)) * 2 * Math.PI - Math.PI / 2
                  const r = outerRadius * 0.6
                  const tx = node.x + Math.cos(angle) * r
                  const ty = node.y + Math.sin(angle) * r

                  // Tag dot
                  ctx.beginPath()
                  ctx.arc(tx, ty, 4 / globalScale, 0, 2 * Math.PI)
                  ctx.fillStyle = node.color || '#6b7280'
                  ctx.globalAlpha = 0.7
                  ctx.fill()
                  ctx.globalAlpha = 1.0

                  // Tag label
                  const tagFontSize = Math.max(8 / globalScale, 2)
                  ctx.font = `${tagFontSize}px sans-serif`
                  ctx.fillStyle = '#374151'
                  ctx.textAlign = 'center'
                  ctx.textBaseline = 'top'
                  const truncTag = tag.length > 16 ? tag.slice(0, 14) + '…' : tag
                  ctx.fillText(truncTag, tx, ty + 5 / globalScale)
                })
              } else if (isGroup) {
                // --- Collapsed group node ---
                const radius = 12
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                ctx.fillStyle = node.color || '#6b7280'
                ctx.fill()

                // Article count badge in the centre
                if (node.articleCount) {
                  const badgeFontSize = Math.max(8 / globalScale, 2)
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
              } else {
                // --- Article node ---
                const radius = 8
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
                ctx.fillStyle = '#10b981'
                ctx.fill()

                const label: string = node.label || node.id
                const truncated = label.length > 22 ? label.slice(0, 20) + '…' : label
                const fontSize = Math.max(11 / globalScale, 3)
                ctx.font = `${fontSize}px sans-serif`
                ctx.fillStyle = '#6b7280'
                ctx.textAlign = 'center'
                ctx.textBaseline = 'top'
                ctx.fillText(truncated, node.x, node.y + radius + 2)
              }
            }}
          />
        </div>
      </div>

      {/* Right panel — 40% */}
      <div className="w-[40%] flex flex-col min-h-0">
        {expandedGroup ? (
          <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
            {/* Panel header */}
            <div
              className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0"
              style={{ borderLeftColor: expandedGroupColor, borderLeftWidth: 3 }}
            >
              <h3 className="text-sm font-semibold text-foreground">{expandedGroupLabel}</h3>
              <button
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => { setExpandedGroup(null); setGroupData([]) }}
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
    </div>
  )
}
