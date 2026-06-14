'use client'

import { useCallback, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { ChatbotPlugin, openaiAdapter, useChat } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme } from '@/lib/providers'

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'

const FLOAT_STORAGE_KEY = 'rag_float_chat_messages'

function loadFloatSession() {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(FLOAT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) })) : []
  } catch {
    return []
  }
}

function saveFloatSession(messages: any[]) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(FLOAT_STORAGE_KEY, JSON.stringify(messages))
  } catch {}
}

export function FloatingChatbotWrapper() {
  const { data: session, status } = useSession()
  const { selectedTopicId } = useTopic()
  const { t } = useI18n()
  const { mode } = useTheme()

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

  const { messages, sendMessage, isLoading, clearMessages } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: openaiAdapter,
    initialMessages: loadFloatSession(),
    headers,
    onError: (err) => {
      const is429 = err.message.includes('429')
      const is503 = err.message.includes('503')
      if (is429) {
        toast.warning(t('rag.rateLimitError'))
      } else if (is503) {
        toast.error(t('rag.serviceUnavailable'))
      } else {
        toast.error(t('rag.genericError'))
      }
    },
  })

  useEffect(() => {
    if (messages.length > 0) {
      saveFloatSession(messages)
    }
  }, [messages])

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      sendMessage(text)
    },
    [sendMessage]
  )

  const handleNewChat = useCallback(() => {
    clearMessages()
    localStorage.removeItem(FLOAT_STORAGE_KEY)
  }, [clearMessages])

  if (status !== 'authenticated') return null

  return (
    <ChatbotPlugin
      theme={mode}
      messages={messages}
      onSend={handleSend}
      isLoading={isLoading}
      onNewChat={handleNewChat}
      title={t('rag.assistantTitle')}
      placeholder={t('rag.placeholder')}
    />
  )
}
