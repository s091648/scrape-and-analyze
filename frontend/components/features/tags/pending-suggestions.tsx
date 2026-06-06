'use client'
import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'
import type { SuggestionOut } from '@/lib/api/tags'
import { approveSuggestion, rejectSuggestion } from '@/lib/api/tags'

interface Props {
  suggestions: SuggestionOut[]
  token: string
  onResolved: (id: string) => void
}

export function PendingSuggestions({ suggestions, token, onResolved }: Props) {
  const { t } = useI18n()
  const [processing, setProcessing] = useState<string | null>(null)
  const [mergingAll, setMergingAll] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(false)

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

  async function handleMergeAll() {
    if (!confirm(t('tags.confirmMergeAll', { count: suggestions.length }))) return
    setMergingAll(true)
    try {
      for (const s of suggestions) {
        await approveSuggestion(s.id, token)
        onResolved(s.id)
      }
    } finally {
      setMergingAll(false)
    }
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/20 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <button
          className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
          onClick={() => setIsCollapsed(c => !c)}
        >
          <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-200">
            {t('tags.pendingMergeSuggestions', { count: suggestions.length })}
          </h3>
          {isCollapsed
            ? <ChevronDown className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
            : <ChevronUp className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
          }
        </button>
        {!isCollapsed && (
          <Button
            size="sm" variant="outline"
            className="h-7 px-3 text-xs border-amber-300 hover:bg-amber-100 dark:border-amber-700 dark:hover:bg-amber-900/40"
            disabled={mergingAll || processing !== null}
            onClick={handleMergeAll}
          >
            {t('tags.mergeAll')}
          </Button>
        )}
      </div>
      {!isCollapsed && (
        <div className="space-y-2">
          {suggestions.map(s => (
            <div key={s.id} className="flex items-center justify-between gap-3 text-sm">
              <div className="min-w-0">
                <span className="font-medium">&ldquo;{s.new_tag_name}&rdquo;</span>
                <span className="text-muted-foreground mx-1">&rarr;</span>
                <span className="font-medium">&ldquo;{s.existing_tag_name}&rdquo;</span>
                <span className="text-muted-foreground ml-2 text-xs">
                  {s.group_name} &middot; {t('tags.similar', { pct: (s.similarity_score * 100).toFixed(0) })}
                </span>
              </div>
              <div className="flex gap-1.5 shrink-0">
                <Button
                  size="sm" variant="outline" className="h-7 px-2 text-xs"
                  disabled={processing === s.id || mergingAll}
                  onClick={() => handle(s.id, 'approve')}
                >
                  {t('tags.merge')}
                </Button>
                <Button
                  size="sm" variant="ghost" className="h-7 px-2 text-xs text-muted-foreground"
                  disabled={processing === s.id || mergingAll}
                  onClick={() => handle(s.id, 'reject')}
                >
                  {t('tags.keepBoth')}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
