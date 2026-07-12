'use client'

import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { AgentInput, openaiAdapter, useChat, type StreamAdapter, type StreamEvent } from '@s091648/chatbot-plugin-ui'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme, useChatQuota, usePinnedArticle } from '@/lib/providers'
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
  const { pinnedArticles, removePinnedArticle } = usePinnedArticle()

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId
  if (pinnedArticles.length > 0) headers['X-Pinned-Article-Ids'] = pinnedArticles.map(a => a.id).join(',')

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
      {pinnedArticles.length > 0 && (
        <div className="mb-1.5 flex flex-wrap gap-1.5">
          {pinnedArticles.map(article => (
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
      <AnswerDisplay messages={messages} isLoading={isLoading} error={error} sources={lastSources} />
    </div>
  )
}
