'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import { CitedContent } from './cited-content'
import type { ConversationTurn } from './types'

interface AnswerDisplayProps {
  turns: ConversationTurn[]
  /** Index into `turns` currently on screen — the parent auto-advances this to the newest turn
   * whenever one settles; the prev/next buttons here only move it temporarily. */
  currentIndex: number
  isLoading?: boolean
  error?: Error | null
  onPrevTurn: () => void
  onNextTurn: () => void
}

function ThinkingBlock({ thinking, toggleLabel }: { thinking: string; toggleLabel: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-3 rounded-lg border border-border overflow-hidden text-xs">
      <button
        className="flex items-center gap-1.5 w-full px-3 py-2 text-left text-muted-foreground hover:bg-muted/50 transition-colors cursor-pointer"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className={`text-[9px] transition-transform duration-150 inline-block ${open ? 'rotate-90' : ''}`}>▶</span>
        {toggleLabel}
      </button>
      {open && (
        <pre className="px-3 py-2 text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap break-words border-t border-border bg-muted/30 font-sans">
          {thinking}
        </pre>
      )}
    </div>
  )
}

export function AnswerDisplay({ turns, currentIndex, isLoading, error, onPrevTurn, onNextTurn }: AnswerDisplayProps) {
  const { t } = useI18n()
  const currentTurn = turns[currentIndex]

  if (isLoading && !currentTurn) {
    return (
      <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm text-muted-foreground animate-pulse">
        {t('rag.thinking')}
      </div>
    )
  }

  if (error && !currentTurn) {
    const is429 = error.message.includes('429')
    const is503 = error.message.includes('503')
    const msg = is429
      ? t('rag.rateLimitError')
      : is503
        ? t('rag.serviceUnavailable')
        : t('rag.genericError')
    return (
      <div className="mt-3 px-4 py-3 rounded-lg bg-destructive/10 text-sm text-destructive">
        {msg}
      </div>
    )
  }

  if (!currentTurn) return null

  // The turn currently streaming in is always the newest one (the parent keeps currentIndex
  // pinned to it) — everything else on screen is a settled, browsable turn.
  const isLive = isLoading && currentIndex === turns.length - 1

  return (
    <>
      {currentTurn.assistantMessage.thinking && (
        <ThinkingBlock thinking={currentTurn.assistantMessage.thinking} toggleLabel={t('rag.thinkingToggle')} />
      )}
      <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm leading-relaxed">
        {currentTurn.userMessage && (
          <p className="mb-1.5 text-xs font-medium text-muted-foreground">{currentTurn.userMessage.content}</p>
        )}
        <CitedContent text={currentTurn.assistantMessage.content} sources={currentTurn.sources} showSourceList={!isLive} />
        {isLive && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-foreground/60 animate-pulse align-middle" />
        )}
      </div>
      {!isLoading && turns.length > 1 && (
        <div className="mt-1 flex items-center justify-end gap-1.5 text-[11px] text-muted-foreground">
          <button
            type="button"
            onClick={onPrevTurn}
            disabled={currentIndex === 0}
            aria-label={t('rag.previousTurn')}
            className="rounded-full p-0.5 hover:bg-muted disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span>{currentIndex + 1} / {turns.length}</span>
          <button
            type="button"
            onClick={onNextTurn}
            disabled={currentIndex === turns.length - 1}
            aria-label={t('rag.nextTurn')}
            className="rounded-full p-0.5 hover:bg-muted disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </>
  )
}
