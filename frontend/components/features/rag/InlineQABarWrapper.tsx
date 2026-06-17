'use client'

import { useCallback, useEffect, useRef } from 'react'
import { useSession } from 'next-auth/react'
import { AgentInput, openaiAdapter, useChat } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme, useChatQuota } from '@/lib/providers'
import { AnswerDisplay } from './AnswerDisplay'

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

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

  const prevIsLoadingRef = useRef(false)

  const { messages, sendMessage, isLoading, error } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: openaiAdapter,
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

  // Re-fetch server quota when response completes (keeps FloatingChatbotWrapper in sync)
  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading) {
      refreshQuota()
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, refreshQuota])

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      sendMessage(text)
    },
    [sendMessage]
  )

  const quotaText = quota && quota.remaining >= 0
    ? `${quota.remaining} / ${quota.limit} ${t('rag.remainingRequests')}`
    : null

  return (
    <div className={className}>
      <AgentInput
        theme={mode}
        onSend={handleSend}
        isLoading={isLoading}
        messages={messages}
        placeholder={placeholder ?? t('rag.placeholder')}
      />
      {quotaText && (
        <p className="mt-1 text-right text-[11px] text-muted-foreground">{quotaText}</p>
      )}
      <AnswerDisplay messages={messages} isLoading={isLoading} error={error} />
    </div>
  )
}
