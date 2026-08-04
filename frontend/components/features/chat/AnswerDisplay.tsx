'use client'

import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Message } from '@s091648/chatbot-plugin-ui'
import { useI18n } from '@/lib/providers'
import { CitedContent } from './cited-content'
import { useTypewriter } from './use-typewriter'
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

function ThinkingBlock({ thinking, toggleLabel, defaultOpen }: { thinking: string; toggleLabel: string; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  // Gemini's thinking-summary deltas arrive as a handful of large blocks (whole paragraphs at
  // once), not token-by-token like the main answer — displaying `thinking` raw makes each block
  // visibly pop in rather than feel like it's streaming. useTypewriter reveals it incrementally
  // regardless of how big each incoming chunk was.
  const displayedThinking = useTypewriter(thinking)
  // Unlike FloatingChatbotPanel's own ThinkingBlock (which sits on that panel's already-solid
  // bg-card), this one renders directly over WeeklyReportWidget's photo/gradient backdrop — a
  // translucent bg-muted/border-border treatment is unreadable there. A solid dark background
  // (matching the tool-call card's own dark theme) keeps it legible regardless of what's behind it.
  return (
    <div className="mb-3 rounded-lg overflow-hidden text-xs bg-neutral-900 text-neutral-200">
      <button
        className="flex items-center gap-1.5 w-full px-3 py-2 text-left hover:bg-neutral-800 transition-colors cursor-pointer"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className={`text-[9px] transition-transform duration-150 inline-block ${open ? 'rotate-90' : ''}`}>▶</span>
        {toggleLabel}
      </button>
      {open && (
        <pre className="px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap break-words border-t border-neutral-700 font-sans">
          {displayedThinking}
        </pre>
      )}
    </div>
  )
}

/** Compact status card per tool call — name, arguments, and a running/done/error badge. Renders
 * in the (properly scrollable) AnswerDisplay area rather than AgentInput's own built-in tool-call
 * card, which renders raw and in full with no truncation or collapse of its own and, fed the
 * complete toolResult.content of even a single search, was enough on its own to blow out that
 * small input-bar area's height. Deliberately omits toolResult.content — the actual search
 * results are already properly surfaced as numbered citations via CitedContent below. */
function ToolCallBlock({ toolCalls, labels }: { toolCalls: Message[]; labels: { running: string; done: string; error: string } }) {
  if (toolCalls.length === 0) return null
  return (
    <div className="mb-3 space-y-1.5">
      {toolCalls.map(m => {
        if (!m.toolCall) return null
        const status = m.toolResult ? (m.toolResult.isError ? 'error' : 'done') : 'running'
        const statusLabel = status === 'error' ? labels.error : status === 'done' ? labels.done : labels.running
        const statusClass = status === 'error' ? 'text-red-400' : status === 'done' ? 'text-green-400' : 'text-amber-400'
        const args = m.toolCall.arguments
        return (
          <div key={m.id} className="rounded-lg overflow-hidden text-xs bg-neutral-900 text-neutral-200">
            <div className="flex items-center justify-between gap-2 px-3 py-2">
              <span className="font-medium truncate">{m.toolCall.name}</span>
              <span className={`shrink-0 ${statusClass}`}>{statusLabel}</span>
            </div>
            {args && Object.keys(args).length > 0 && (
              <pre className="px-3 pb-2 text-[11px] leading-relaxed whitespace-pre-wrap break-words font-sans opacity-80">
                {JSON.stringify(args)}
              </pre>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function AnswerDisplay({ turns, currentIndex, isLoading, error, onPrevTurn, onNextTurn, hasUnreadResponse, draggableSources }: AnswerDisplayProps) {
  const { t } = useI18n()
  const currentTurn = turns[currentIndex]

  // Same reasoning as ThinkingBlock's — the main answer streams in bigger network chunks than a
  // smooth per-character reveal, so this evens it out into a typewriter-style animation. Must
  // sit before every early return below (Rules of Hooks — this component isn't remounted per
  // turn, so a hook call can't be conditional on any of those branches), which is why it reads
  // directly off `turns[currentIndex]` rather than `currentTurn.assistantMessage` — not yet
  // guaranteed to exist this early (see the `!currentTurn.assistantMessage` branch further down).
  const displayedContent = useTypewriter(turns[currentIndex]?.assistantMessage?.content ?? '')

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
  // The network stream can finish (isLoading flips false) while the typewriter is still
  // catching up to the final text — the cursor and source list should wait for the visible
  // reveal to actually finish, not just for the underlying fetch to.
  const stillTyping = isLive && displayedContent !== (currentTurn.assistantMessage?.content ?? '')
  const isLiveLoading = (isLoading && isLive) || stillTyping

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
      <ToolCallBlock
        toolCalls={currentTurn.toolCalls ?? []}
        labels={{ running: t('rag.toolStatusRunning'), done: t('rag.toolStatusDone'), error: t('rag.toolStatusError') }}
      />
      <div className="mt-3 px-4 py-3 rounded-lg bg-white/55 backdrop-blur-md text-sm leading-relaxed text-neutral-800">
        {currentTurn.userMessage && (
          <p className="mb-1.5 text-xs font-medium text-neutral-600">{currentTurn.userMessage.content}</p>
        )}
        {currentTurn.assistantMessage.thinking && (
          // Keyed by message id so switching turns (via the pager) mounts a fresh block with its
          // own open/closed state, instead of reusing one instance whose state was left over from
          // a different turn. defaultOpen only matters at that mount — open while this turn is the
          // one actively streaming, so its thinking is actually visible growing in real time
          // instead of needing a click to reveal everything at once after the fact.
          <ThinkingBlock
            key={currentTurn.assistantMessage.id}
            thinking={currentTurn.assistantMessage.thinking}
            toggleLabel={t('rag.thinkingToggle')}
            defaultOpen={isLiveLoading}
          />
        )}
        <CitedContent
          text={displayedContent}
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
