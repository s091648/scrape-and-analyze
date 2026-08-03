'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import { CitedContent } from './cited-content'
import type { ConversationTurn } from './types'

interface AnswerDisplayProps {
  turns: ConversationTurn[]
  /** Index into `turns` currently on screen — the parent auto-advances this to the newest turn
   * whenever a new question is asked; the prev/next buttons here only move it temporarily. */
  currentIndex: number
  isLoading?: boolean
  error?: Error | null
  onPrevTurn: () => void
  onNextTurn: () => void
  /** See ChatConversationSnapshot.hasUnreadResponse — renders a red dot on the "next" button. */
  hasUnreadResponse?: boolean
  /** Makes each source-chip pill in the answer a dnd-kit drag source (see CitedContent). Default
   * false — only meaningful when the caller renders this inside its own DndContext. */
  draggableSources?: boolean
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

export function AnswerDisplay({ turns, currentIndex, isLoading, error, onPrevTurn, onNextTurn, hasUnreadResponse, draggableSources }: AnswerDisplayProps) {
  const { t } = useI18n()
  const currentTurn = turns[currentIndex]

  // No turn at all yet (not even a pending one) — the very first question in the conversation,
  // before InlineQABarWrapper has anything to report.
  if (isLoading && !currentTurn) {
    return (
      <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm text-neutral-600 animate-pulse">
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
      <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm text-destructive">
        {msg}
      </div>
    )
  }

  if (!currentTurn) return null

  // The newest turn, regardless of whether it's still streaming — used to scope the loading
  // cursor / red dot to it and to keep the pager's position label correct.
  const isLive = currentIndex === turns.length - 1
  const isLiveLoading = isLoading && isLive

  const pager = turns.length > 1 && (
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
        className="relative rounded-full p-0.5 hover:bg-muted disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
      >
        <ChevronRight className="h-3.5 w-3.5" />
        {hasUnreadResponse && currentIndex !== turns.length - 1 && (
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 animate-notify-blink rounded-full bg-red-500 ring-1 ring-background" />
        )}
      </button>
    </div>
  )

  // The question has been sent but no reply has come back at all yet — its own turn already
  // exists (see InlineQABarWrapper's `turns`) so the page switches to it immediately instead of
  // waiting for the first byte of a reply.
  if (!currentTurn.assistantMessage) {
    if (isLive && error) {
      const is429 = error.message.includes('429')
      const is503 = error.message.includes('503')
      const msg = is429
        ? t('rag.rateLimitError')
        : is503
          ? t('rag.serviceUnavailable')
          : t('rag.genericError')
      return (
        <>
          <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm text-destructive">
            {currentTurn.userMessage && (
              <p className="mb-1.5 text-xs font-medium text-neutral-600">{currentTurn.userMessage.content}</p>
            )}
            {msg}
          </div>
          {pager}
        </>
      )
    }
    return (
      <>
        <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm text-neutral-600 animate-pulse">
          {currentTurn.userMessage && (
            <p className="mb-1.5 text-xs font-medium text-neutral-600">{currentTurn.userMessage.content}</p>
          )}
          {t('rag.thinking')}
        </div>
        {pager}
      </>
    )
  }

  return (
    <>
      {currentTurn.assistantMessage.thinking && (
        <ThinkingBlock thinking={currentTurn.assistantMessage.thinking} toggleLabel={t('rag.thinkingToggle')} />
      )}
      <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm leading-relaxed text-neutral-800">
        {currentTurn.userMessage && (
          <p className="mb-1.5 text-xs font-medium text-neutral-600">{currentTurn.userMessage.content}</p>
        )}
        <CitedContent
          text={currentTurn.assistantMessage.content}
          sources={currentTurn.sources}
          showSourceList={!isLiveLoading}
          draggableSources={draggableSources}
        />
        {isLiveLoading && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-neutral-800/60 animate-pulse align-middle" />
        )}
      </div>
      {pager}
    </>
  )
}
