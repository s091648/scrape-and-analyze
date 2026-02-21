'use client'
import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { apiFetch } from '@/lib/api-fetch'

const ForceGraph = dynamic(() => import('react-force-graph-2d'), { ssr: false })

interface GraphNode { id: string; type: 'tag' | 'article'; label: string; articleId?: string }
interface GraphEdge { source: string; target: string }
interface GraphData { nodes: GraphNode[]; edges: GraphEdge[] }

export function KnowledgeGraph() {
  const [days, setDays] = useState(30)
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] })
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [tagArticles, setTagArticles] = useState<any[]>([])

  useEffect(() => {
    apiFetch(`/analyses/graph?days=${days}`)
      .then(r => r.json())
      .then(data => setGraphData({ nodes: data.nodes, edges: data.edges }))
  }, [days])

  function handleNodeClick(node: any) {
    if (node.type === 'tag') {
      setSelectedTag(node.label)
      apiFetch(`/analyses/graph/tag/${encodeURIComponent(node.label)}`)
        .then(r => r.json())
        .then(setTagArticles)
    }
  }

  return (
    <div className="flex gap-4">
      <div className="flex-1">
        <div className="mb-4 flex items-center gap-2">
          <label>Time window:</label>
          <select value={days} onChange={e => setDays(Number(e.target.value))}>
            {[7, 30, 90, 180].map(d => <option key={d} value={d}>{d} days</option>)}
          </select>
        </div>
        <ForceGraph
          graphData={{ nodes: graphData.nodes, links: graphData.edges }}
          nodeColor={(node: any) => node.type === 'tag' ? '#6366f1' : '#10b981'}
          nodeRelSize={6}
          onNodeClick={handleNodeClick}
          nodeCanvasObject={(node: any, ctx) => {
            const size = node.type === 'tag' ? 8 : 5
            ctx.beginPath()
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI)
            ctx.fillStyle = node.type === 'tag' ? '#6366f1' : '#10b981'
            ctx.fill()
          }}
        />
      </div>
      {selectedTag && tagArticles.length > 0 && (
        <aside className="w-80 border-l pl-4">
          <h3 className="font-semibold mb-2">#{selectedTag}</h3>
          <ul className="space-y-3">
            {tagArticles.map((a: any) => (
              <li key={a.articleId} className="text-sm">
                <a href={a.url} target="_blank" className="font-medium hover:underline">{a.title}</a>
                <p className="text-muted-foreground">{a.excerpt}</p>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  )
}
