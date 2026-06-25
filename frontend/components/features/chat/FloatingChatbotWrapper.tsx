'use client'

import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { openaiAdapter, useChat, type StreamAdapter, type StreamEvent, type Message } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme, useGuestMode, useChatQuota } from '@/lib/providers'
import { FloatingChatbotPanel, type ArticleSource } from './FloatingChatbotPanel'

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'
const FLOAT_STORAGE_KEY = 'rag_float_chat_messages'

function loadFloatSession(userId: string): Message[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(FLOAT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    // Discard if stored for a different user (prevents guest→auth carry-over)
    if (parsed.userId !== userId) return []
    return Array.isArray(parsed.messages)
      ? parsed.messages.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }))
      : []
  } catch {
    return []
  }
}

function saveFloatSession(userId: string, messages: Message[]) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(FLOAT_STORAGE_KEY, JSON.stringify({ userId, messages }))
  } catch {}
}

export function FloatingChatbotWrapper() {
  const { data: session, status } = useSession()
  const { selectedTopicId } = useTopic()
  const { t } = useI18n()
  const { mode } = useTheme()
  const { isGuestMode } = useGuestMode()
  const { quota, refreshQuota } = useChatQuota()
  const [messageSources, setMessageSources] = useState<Record<string, ArticleSource[]>>({})

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

  // 'guest' for unauthenticated; actual user id for authenticated
  const userId = status === 'authenticated'
    ? (((session?.user as any)?.id as string) ?? 'guest')
    : 'guest'

  // Captures sources SSE event emitted after the content chunks
  const pendingSourcesRef = useRef<ArticleSource[]>([])
  const prevIsLoadingRef = useRef(false)

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

  const { messages, sendMessage, isLoading, clearMessages, abort } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: customAdapter,
    initialMessages: loadFloatSession(userId),
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

  // When stream finishes: associate pending sources + re-fetch server quota
  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading) {
      // Capture the array reference BEFORE clearing the ref — the functional updater
      // passed to setMessageSources is called during the next render, by which point
      // pendingSourcesRef.current would already be [] if we cleared it first.
      const captured = pendingSourcesRef.current
      pendingSourcesRef.current = []
      const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')
      if (captured.length > 0) {
        if (lastAssistant) {
          setMessageSources(s => ({ ...s, [lastAssistant.id]: captured }))
        }
      }
      // Stream ended with an empty assistant message → upstream LLM failure
      if (lastAssistant && !lastAssistant.content?.trim()) {
        toast.error(t('rag.serviceUnavailable'))
      }
      // Re-fetch actual server quota (reflects InlineQABarWrapper usage too)
      refreshQuota()
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, messages, refreshQuota])

  // Persist messages to localStorage, tagged with current userId
  useEffect(() => {
    if (messages.length > 0) {
      saveFloatSession(userId, messages)
    }
  }, [messages, userId])

  // Clear history on logout so the next user starts fresh
  useEffect(() => {
    if (status === 'unauthenticated') {
      localStorage.removeItem(FLOAT_STORAGE_KEY)
    }
  }, [status])

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
    setMessageSources({})
  }, [clearMessages])

  // Hide during session resolution
  if (status === 'loading') return null
  // Unauthenticated users only see the chatbot when explicitly in guest mode
  if (status === 'unauthenticated' && !isGuestMode) return null

  const quotaSuffix = quota !== null && quota.remaining >= 0
    ? ` · ${quota.remaining}/${quota.limit}`
    : ''

  return (
    <FloatingChatbotPanel
      theme={mode}
      messages={messages}
      messageSources={messageSources}
      onSend={handleSend}
      isLoading={isLoading}
      onNewChat={handleNewChat}
      onAbort={abort}
      title={`${t('rag.assistantTitle')}${quotaSuffix}`}
      placeholder={t('rag.placeholder')}
    />
  )
}
