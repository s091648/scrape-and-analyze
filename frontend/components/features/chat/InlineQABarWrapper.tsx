'use client'

import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { useDroppable } from '@dnd-kit/core'
import { AgentInput, openaiAdapter, useChat, type StreamAdapter, type StreamEvent } from '@s091648/chatbot-plugin-ui'
import { Inbox, Pencil, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme, useChatQuota, usePinnedArticle } from '@/lib/providers'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import type { ArticleSource, ChatConversationSnapshot, ConversationTurn } from './types'

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

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'

export function InlineQABarWrapper({ placeholder, className, onMessageSent, onConversationChange }: InlineQABarWrapperProps) {
  const { data: session } = useSession()
  const { selectedTopicId } = useTopic()
  const { t } = useI18n()
  const { mode } = useTheme()
  const { quota, refreshQuota } = useChatQuota()
  const { pinnedArticles, removePinnedArticle, pinnedGroups = [], toggleGroupArticle, removeGroup, isPinned } = usePinnedArticle()
  const { setNodeRef: setDropRef, isOver } = useDroppable({ id: 'chat-input-dropzone' })

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId
  if (pinnedArticles.length > 0) headers['X-Pinned-Article-Ids'] = pinnedArticles.map(a => a.id).join(',')

  // Articles pinned individually (not part of a weekly-report batch) still render as their own pill.
  const groupedArticleIds = new Set(pinnedGroups.flatMap(g => g.articles.map(a => a.id)))
  const individualPills = pinnedArticles.filter(a => !groupedArticleIds.has(a.id))

  const pendingSourcesRef = useRef<ArticleSource[]>([])
  const prevIsLoadingRef = useRef(false)
  // Sources for every settled turn, keyed by that turn's assistant message id — unlike a single
  // "latest sources" value, this survives paging back to an earlier turn (see ConversationTurn).
  const [sourcesByMessageId, setSourcesByMessageId] = useState<Record<string, ArticleSource[]>>({})
  const [currentTurnIndex, setCurrentTurnIndex] = useState(0)

  const customAdapter = useMemo((): StreamAdapter => ({
    ...openaiAdapter,
    parse(line: string): StreamEvent | null {
      if (line.startsWith('data: ') && !line.includes('[DONE]')) {
        try {
          const json = JSON.parse(line.slice(6).trim())
          if (Array.isArray(json.sources)) {
            pendingSourcesRef.current = json.sources
            return null
          }
          if (typeof json.thinking === 'string') {
            return { type: 'thinking_delta', content: json.thinking }
          }
        } catch {}
      }
      return openaiAdapter.parse(line)
    },
  }), [])

  const { messages, sendMessage, isLoading, error, abort } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: customAdapter,
    headers,
    onError: (err) => {
      if (err.message.includes('429')) {
        toast.warning(t('rag.rateLimitError'))
        refreshQuota()
      } else if (err.message.includes('503')) {
        toast.error(t('rag.serviceUnavailable'))
      } else {
        toast.error(t('rag.genericError'))
      }
    },
  })

  // Every user/assistant message pair, oldest first — lets AnswerDisplay page back through
  // settled turns instead of only ever showing the latest one. The still-streaming message (if
  // any) falls back to pendingSourcesRef directly: sourcesByMessageId only gets a message's
  // entry once its response fully settles, but the backend sends sources early in the stream
  // (retrieval happens before generation), so inline [N] citations can — and should — already be
  // clickable while the answer is still typing in, not just after it finishes.
  const turns = useMemo((): ConversationTurn[] => {
    const result: ConversationTurn[] = []
    let pendingUser: typeof messages[number] | undefined
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i]
      if (m.role === 'user') {
        pendingUser = m
      } else if (m.role === 'assistant') {
        const isLiveMessage = isLoading && i === messages.length - 1
        const sources = sourcesByMessageId[m.id] ?? (isLiveMessage ? pendingSourcesRef.current : [])
        result.push({ userMessage: pendingUser, assistantMessage: m, sources })
        pendingUser = undefined
      }
    }
    return result
  }, [messages, sourcesByMessageId, isLoading])

  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading) {
      const justFinished = [...messages].reverse().find(m => m.role === 'assistant')
      if (justFinished) {
        setSourcesByMessageId(prev => ({ ...prev, [justFinished.id]: pendingSourcesRef.current }))
      }
      pendingSourcesRef.current = []
      refreshQuota()
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, messages, refreshQuota])

  // A newly-settled turn always becomes the visible one — jumping back to an older turn is a
  // manual, temporary detour, not a state that should survive the next question being answered.
  useEffect(() => {
    setCurrentTurnIndex(Math.max(0, turns.length - 1))
  }, [turns.length])

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
      onPrevTurn: () => setCurrentTurnIndex(i => Math.max(0, i - 1)),
      onNextTurn: () => setCurrentTurnIndex(i => Math.min(turns.length - 1, i + 1)),
    })
    // onConversationChange intentionally excluded: it's a plain callback prop, not expected to
    // be memoized by the caller — including it would re-report on every parent render for no
    // reason. Every value the snapshot is actually built from is listed below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns, currentTurnIndex, isLoading, error])

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      onMessageSent?.()
      sendMessage(text)
    },
    [sendMessage, onMessageSent]
  )

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
          messages={messages}
          placeholder={placeholder ?? t('rag.placeholder')}
          labels={{
            inputAriaLabel: t('rag.agentInputAriaLabel'),
            sendAriaLabel: t('rag.agentSendAriaLabel'),
            send: t('rag.agentSend'),
            sendLoading: t('rag.agentSendLoading'),
            toolCallCard: {
              statusRunning: t('rag.toolStatusRunning'),
              statusDone: t('rag.toolStatusDone'),
              statusError: t('rag.toolStatusError'),
            },
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
                      <div className="flex max-h-56 flex-col gap-1.5 overflow-y-auto">
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
