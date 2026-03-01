'use client'
import { useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { apiFetch } from '@/lib/api-fetch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ExternalLink, X } from 'lucide-react'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), { ssr: false })

interface GraphNode { id: string; type: 'tag' | 'article'; label: string; articleId?: string }
interface GraphEdge { source: string; target: string }
interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

interface TagArticle {
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
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [tagArticles, setTagArticles] = useState<TagArticle[]>([])

  const graphContainerRef = useRef<HTMLDivElement>(null)
  const [graphDims, setGraphDims] = useState({ width: 600, height: 500 })

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
    if (node.type === 'tag') {
      setSelectedTag(node.label)
      apiFetch(`/analyses/graph/tag/${encodeURIComponent(node.label)}`)
        .then(r => r.json())
        .then(setTagArticles)
    }
  }

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
              const isTag = node.type === 'tag'
              const radius = isTag ? 8 : 5

              // Circle
              ctx.beginPath()
              ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
              ctx.fillStyle = isTag ? '#6366f1' : '#10b981'
              ctx.fill()

              // Label below circle
              const label: string = node.label || node.id
              const truncated = label.length > 22 ? label.slice(0, 20) + '…' : label
              const fontSize = Math.max((isTag ? 11 : 9) / globalScale, isTag ? 3 : 2)
              ctx.font = `${isTag ? 'bold ' : ''}${fontSize}px sans-serif`
              ctx.fillStyle = isTag ? '#6366f1' : '#6b7280'
              ctx.textAlign = 'center'
              ctx.textBaseline = 'top'
              ctx.fillText(truncated, node.x, node.y + radius + 2)
            }}
          />
        </div>
      </div>

      {/* Right panel — 40% */}
      <div className="w-[40%] flex flex-col min-h-0">
        {selectedTag ? (
          <div className="flex flex-col h-full border border-border rounded-xl bg-card overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <h3 className="text-sm font-semibold text-foreground">#{selectedTag}</h3>
              <button
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setSelectedTag(null)}
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <ScrollArea className="flex-1">
              <ul className="p-4 space-y-4">
                {tagArticles.map(a => (
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
            </ScrollArea>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center border border-dashed border-border rounded-xl text-sm text-muted-foreground">
            Click a node to explore
          </div>
        )}
      </div>
    </div>
  )
}
