'use client'

import { useEffect, useMemo } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { AgentInput } from '@s091648/chatbot-plugin-ui'
import { Inbox, Pencil, Sparkles, X } from 'lucide-react'
import { useI18n, useTheme, useChatQuota, usePinnedReport, useInlineChat } from '@/lib/providers'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import type { ChatConversationSnapshot } from './types'

interface InlineQABarWrapperProps {
  placeholder?: string
  className?: string
  /** Called when a message is sent — lets a wrapping component (the weekly report widget)
   * react to the conversation starting/advancing without owning the chat state itself. */
  onMessageSent?: () => void
  /** Reports the live conversation state on every change — lets a wrapping component render the
   * answer panel (e.g. AnswerDisplay) somewhere else in the tree, since this component owns the
   * actual useChat() state but the answer panel is a sibling, not a descendant, of this input bar. */
  onConversationChange?: (snapshot: ChatConversationSnapshot) => void
}

export function InlineQABarWrapper({ placeholder, className, onMessageSent, onConversationChange }: InlineQABarWrapperProps) {
  const { t } = useI18n()
  const { mode } = useTheme()
  const { quota } = useChatQuota()
  const { pinnedArticles, removePinnedArticle, pinnedGroups = [], toggleGroupArticle, removeGroup, isPinned } = usePinnedReport()
  const { setNodeRef: setDropRef, isOver } = useDroppable({ id: 'chat-input-dropzone' })

  const {
    messages,
    turns,
    currentTurnIndex,
    isLoading,
    error,
    hasUnreadResponse,
    onPrevTurn,
    onNextTurn,
    onSend: sendMessage,
    onAbort: abort,
  } = useInlineChat()

  // Articles pinned individually (not part of a weekly-report batch) still render as their own pill.
  const groupedArticleIds = new Set(pinnedGroups.flatMap(g => g.articles.map(a => a.id)))
  const individualPills = pinnedArticles.filter(a => !groupedArticleIds.has(a.id))

  // AgentInput's only use of `messages` is rendering every role:'tool' entry as an always-expanded
  // card (raw JSON args + full result, no collapse control of its own) in its own small
  // toolCallsArea — which is what used to blow out this input bar's height. Tool-call activity now
  // renders properly (scoped per-turn, with a status badge, no raw result dump) inside AnswerDisplay
  // instead — see ToolCallBlock in AnswerDisplay.tsx — so AgentInput no longer needs to see them at all.
  const agentInputMessages = useMemo(() => messages.filter(m => m.role !== 'tool'), [messages])

  useEffect(() => {
    if (!isLoading) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') abort() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isLoading, abort])

  useEffect(() => {
    onConversationChange?.({
      turns,
      currentIndex: currentTurnIndex,
      isLoading,
      error,
      hasUnreadResponse,
      onPrevTurn,
      onNextTurn,
    })
    // onConversationChange intentionally excluded: it's a plain callback prop, not expected to
    // be memoized by the caller — including it would re-report on every parent render for no
    // reason. Every value the snapshot is actually built from is listed below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns, currentTurnIndex, isLoading, error, hasUnreadResponse])

  const handleSend = (text: string) => {
    if (!text.trim()) return
    onMessageSent?.()
    sendMessage(text)
  }

  const quotaText = quota && quota.remaining >= 0
    ? `${quota.remaining} / ${quota.limit} ${t('rag.remainingRequests')}`
    : null

  return (
    <div className={className}>
      <div
        ref={setDropRef}
        className={`relative rounded-xl transition-all duration-150 ${
          isOver ? 'ring-2 ring-purple-400 bg-purple-50/80 scale-[1.01] dark:bg-purple-950/40' : ''
        }`}
      >
        <AgentInput
          theme={mode}
          onSend={handleSend}
          isLoading={isLoading}
          messages={agentInputMessages}
          placeholder={placeholder ?? t('rag.placeholder')}
          labels={{
            inputAriaLabel: t('rag.agentInputAriaLabel'),
            sendAriaLabel: t('rag.agentSendAriaLabel'),
            send: t('rag.agentSend'),
            sendLoading: t('rag.agentSendLoading'),
          }}
        />
        {isOver && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center gap-1.5 rounded-xl bg-purple-100/90 text-xs font-medium text-purple-700 dark:bg-purple-900/80 dark:text-purple-200">
            <Inbox className="h-3.5 w-3.5" />
            {t('rag.dropToPin')}
          </div>
        )}
        {quotaText && (
          <p className="mt-1 text-right text-[11px] text-muted-foreground">{quotaText}</p>
        )}
        {(pinnedGroups.length > 0 || individualPills.length > 0) && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {pinnedGroups.map(group => {
              const includedCount = group.articles.filter(a => isPinned(a.id)).length
              return (
                <span
                  key={group.id}
                  className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-[11px] text-purple-700 dark:text-purple-300"
                >
                  <Sparkles className="h-2.5 w-2.5 shrink-0" />
                  <span className="truncate max-w-[160px]">{t('rag.weeklyGroupPill', { date: group.dateLabel, count: includedCount })}</span>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        aria-label={t('rag.editGroupArticles')}
                        className="cursor-pointer rounded-full hover:bg-purple-200 dark:hover:bg-purple-800/60 p-0.5"
                      >
                        <Pencil className="h-2.5 w-2.5" />
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-64">
                      <p className="mb-2 text-xs font-medium">{t('rag.groupArticlesPopoverTitle')}</p>
                      <div className="themed-scrollbar flex max-h-56 flex-col gap-1.5 overflow-y-auto">
                        {group.articles.map((article, idx) => (
                          <label key={article.id} className="flex cursor-pointer items-center gap-2 text-xs">
                            <Checkbox
                              checked={isPinned(article.id)}
                              onCheckedChange={() => toggleGroupArticle(group.id, article.id)}
                            />
                            <span className="inline-flex h-[1.1rem] min-w-[1.1rem] shrink-0 items-center justify-center rounded-full bg-blue-100 text-[9px] font-bold text-blue-600 dark:bg-blue-900/50 dark:text-blue-400">
                              {idx + 1}
                            </span>
                            <span className="truncate">{article.title}</span>
                          </label>
                        ))}
                      </div>
                    </PopoverContent>
                  </Popover>
                  <button
                    type="button"
                    onClick={() => removeGroup(group.id)}
                    aria-label={t('rag.removeArticleRef')}
                    className="cursor-pointer rounded-full hover:bg-purple-200 dark:hover:bg-purple-800/60 p-0.5"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              )
            })}
            {individualPills.map(article => (
              <span
                key={article.id}
                className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/40 text-[11px] text-purple-700 dark:text-purple-300"
              >
                <span className="truncate max-w-[160px]">{article.title}</span>
                <button
                  type="button"
                  onClick={() => removePinnedArticle(article.id)}
                  aria-label={t('rag.removeArticleRef')}
                  className="cursor-pointer rounded-full hover:bg-purple-200 dark:hover:bg-purple-800/60 p-0.5"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
