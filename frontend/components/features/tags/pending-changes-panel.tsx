'use client'
import { useState, useEffect } from 'react'
import { ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'

interface PendingChangesPanelProps {
  count: number
  confirming: boolean
  onConfirm: () => void
  onDiscard: () => void
}

export function PendingChangesPanel({ count, confirming, onConfirm, onDiscard }: PendingChangesPanelProps) {
  const { t } = useI18n()
  const [currentIdx, setCurrentIdx] = useState(-1)

  useEffect(() => {
    setCurrentIdx(-1)
  }, [count])

  function navigateNext() {
    const els = Array.from(document.querySelectorAll<HTMLElement>('[data-pending-change]'))
    if (els.length === 0) return
    const next = (currentIdx + 1) % els.length
    setCurrentIdx(next)
    els[next].scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 bg-card border border-border rounded-xl shadow-lg px-4 py-3 flex items-center gap-3 animate-in slide-in-from-bottom-2">
      <button
        onClick={navigateNext}
        className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors whitespace-nowrap"
      >
        {t('tags.pendingChanges', { count })}
        <ChevronRight className="h-3 w-3" />
      </button>
      <Button
        variant="ghost" size="sm" className="h-7 text-xs"
        onClick={onDiscard}
        disabled={confirming}
      >
        {t('tags.discardMoves')}
      </Button>
      <Button
        size="sm" className="h-7 text-xs"
        onClick={onConfirm}
        disabled={confirming}
      >
        {confirming ? '…' : t('tags.confirmMoves')}
      </Button>
    </div>
  )
}
