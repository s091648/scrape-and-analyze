'use client'
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
  return (
    <div className="fixed bottom-4 right-4 z-50 bg-card border border-border rounded-xl shadow-lg px-4 py-3 flex items-center gap-3 animate-in slide-in-from-bottom-2">
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {t('tags.pendingChanges', { count })}
      </span>
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
