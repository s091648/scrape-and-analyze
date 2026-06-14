'use client'

import { useCallback } from 'react'
import { useSession } from 'next-auth/react'
import { AgentInput, openaiAdapter, useChat } from '@s091648/chatbot-plugin-ui'
import { useI18n, useTopic, useTheme } from '@/lib/providers'
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

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

  const { messages, sendMessage, isLoading, error } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: openaiAdapter,
    headers,
    onError: (err) => {
      console.error('[InlineQABarWrapper] chat error:', err.message)
    },
  })

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      sendMessage(text)
    },
    [sendMessage]
  )

  return (
    <div className={className}>
      <AgentInput
        theme={mode}
        onSend={handleSend}
        isLoading={isLoading}
        messages={messages}
        placeholder={placeholder ?? t('rag.placeholder')}
      />
      <AnswerDisplay messages={messages} isLoading={isLoading} error={error} />
    </div>
  )
}
