'use client'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import type { SuggestionOut } from '@/lib/api/tags'
import { approveSuggestion, rejectSuggestion } from '@/lib/api/tags'

interface Props {
  suggestions: SuggestionOut[]
  token: string
  onResolved: (id: string) => void
}

export function PendingSuggestions({ suggestions, token, onResolved }: Props) {
  const [processing, setProcessing] = useState<string | null>(null)

  if (suggestions.length === 0) return null

  async function handle(id: string, action: 'approve' | 'reject') {
    setProcessing(id)
    try {
      if (action === 'approve') await approveSuggestion(id, token)
      else await rejectSuggestion(id, token)
      onResolved(id)
    } finally {
      setProcessing(null)
    }
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/20 p-5 space-y-3">
      <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-200">
        Pending Merge Suggestions ({suggestions.length})
      </h3>
      <div className="space-y-2">
        {suggestions.map(s => (
          <div key={s.id} className="flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0">
              <span className="font-medium">&ldquo;{s.new_tag_name}&rdquo;</span>
              <span className="text-muted-foreground mx-1">&rarr;</span>
              <span className="font-medium">&ldquo;{s.existing_tag_name}&rdquo;</span>
              <span className="text-muted-foreground ml-2 text-xs">
                {s.group_name} &middot; {(s.similarity_score * 100).toFixed(0)}% similar
              </span>
            </div>
            <div className="flex gap-1.5 shrink-0">
              <Button
                size="sm" variant="outline" className="h-7 px-2 text-xs"
                disabled={processing === s.id}
                onClick={() => handle(s.id, 'approve')}
              >
                Merge
              </Button>
              <Button
                size="sm" variant="ghost" className="h-7 px-2 text-xs text-muted-foreground"
                disabled={processing === s.id}
                onClick={() => handle(s.id, 'reject')}
              >
                Keep both
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
