'use client'
import { useState } from 'react'
import { X, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Keyword {
  id: string
  keyword: string
}

export function ArxivKeywordManager({
  keywords,
  onAdd,
  onDelete,
}: {
  keywords: Keyword[]
  onAdd: (keyword: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const [input, setInput] = useState('')
  const [adding, setAdding] = useState(false)

  async function handleAdd() {
    const trimmed = input.trim()
    if (!trimmed) return
    setAdding(true)
    await onAdd(trimmed)
    setInput('')
    setAdding(false)
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Query Keywords</p>
      <div className="flex flex-wrap gap-2 min-h-6">
        {keywords.length === 0 && (
          <p className="text-xs text-muted-foreground italic">No keywords yet — add one below.</p>
        )}
        {keywords.map(kw => (
          <span
            key={kw.id}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted text-sm font-mono"
          >
            {kw.keyword}
            <button
              onClick={() => onDelete(kw.id)}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label={`Remove keyword ${kw.keyword}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="h-9 px-3 rounded-lg border border-border bg-background text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-ring font-mono"
          placeholder='e.g. ti:"machine learning"'
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAdd() } }}
        />
        <Button
          size="sm"
          variant="outline"
          onClick={handleAdd}
          disabled={adding || !input.trim()}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
