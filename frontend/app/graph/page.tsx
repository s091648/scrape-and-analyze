import { KnowledgeGraph } from '@/components/knowledge-graph'

export default function GraphPage() {
  return (
    <div className="flex flex-col gap-6 h-full">
      <div className="flex items-center gap-3 border-b border-border pb-6">
        <h1 className="text-2xl font-bold leading-none">Knowledge Graph</h1>
      </div>
      <KnowledgeGraph />
    </div>
  )
}
