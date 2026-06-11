'use client'

import { useCallback, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { ChatbotPlugin, openaiAdapter, useChat } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useTopic } from '@/lib/providers'
import { loadSession, saveSession } from '@/lib/chat-session'

const FLOAT_SESSION_KEY = 'rag_float_chat_messages'

function loadFloatSession() {
  if (typeof window === 'undefined') return []
  try {
    const raw = sessionStorage.getItem(FLOAT_SESSION_KEY)
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
    sessionStorage.setItem(FLOAT_SESSION_KEY, JSON.stringify(messages))
  } catch {}
}

export function FloatingChatbotWrapper() {
  const { data: session } = useSession()
  const { selectedTopicId } = useTopic()

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

  const { messages, sendMessage, isLoading } = useChat({
    endpoint: '/api/proxy/chat/completions',
    streamAdapter: openaiAdapter,
    initialMessages: loadFloatSession(),
    headers,
    onError: (err) => {
      const is429 = err.message.includes('429')
      const is503 = err.message.includes('503')
      if (is429) {
        toast.warning('已達每日問答上限')
      } else if (is503) {
        toast.error('問答服務暫時無法使用，請稍後再試')
      } else {
        toast.error('發生錯誤，請稍後再試')
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

  return (
    <ChatbotPlugin
      messages={messages}
      onSend={handleSend}
      isLoading={isLoading}
      title="AI 研究助理"
      placeholder="詢問 AI：最近有哪些相關研究？"
    />
  )
}
