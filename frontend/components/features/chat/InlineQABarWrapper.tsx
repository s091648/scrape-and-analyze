'use client'

import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { useDroppable } from '@dnd-kit/core'
import { AgentInput, openaiAdapter, useChat, type StreamAdapter, type StreamEvent } from '@s091648/chatbot-plugin-ui'
import { Pencil, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme, useChatQuota, usePinnedArticle } from '@/lib/providers'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Checkbox } from '@/components/ui/checkbox'
import { AnswerDisplay } from './AnswerDisplay'
import type { ArticleSource } from './types'

interface InlineQABarWrapperProps {
  placeholder?: string
  className?: string
}

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'

export function InlineQABarWrapper({ placeholder, className }: InlineQABarWrapperProps) {
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
  const [lastSources, setLastSources] = useState<ArticleSource[]>([])

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

  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading) {
      setLastSources(pendingSourcesRef.current)
      pendingSourcesRef.current = []
      refreshQuota()
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, refreshQuota])

  useEffect(() => {
    if (!isLoading) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') abort() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isLoading, abort])

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      setLastSources([])
      sendMessage(text)
    },
    [sendMessage]
  )

  const quotaText = quota && quota.remaining >= 0
    ? `${quota.remaining} / ${quota.limit} ${t('rag.remainingRequests')}`
    : null

  return (
    <div className={className}>
      <div
        ref={setDropRef}
        className={`rounded-xl transition-colors ${isOver ? 'ring-2 ring-purple-300 bg-purple-50/50 dark:bg-purple-950/20' : ''}`}
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
                        {group.articles.map(article => (
                          <label key={article.id} className="flex cursor-pointer items-center gap-2 text-xs">
                            <Checkbox
                              checked={isPinned(article.id)}
                              onCheckedChange={() => toggleGroupArticle(group.id, article.id)}
                            />
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
      <AnswerDisplay messages={messages} isLoading={isLoading} error={error} sources={lastSources} />
    </div>
  )
}
