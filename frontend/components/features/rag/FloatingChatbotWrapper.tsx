'use client'

import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { useSession } from 'next-auth/react'
import { openaiAdapter, useChat, type StreamAdapter, type StreamEvent, type Message } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n, useTopic, useTheme } from '@/lib/providers'
import { FloatingChatbotPanel, type ArticleSource } from './FloatingChatbotPanel'

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'
const QUOTA_ENDPOINT = '/api/proxy/chat/quota'
const FLOAT_STORAGE_KEY = 'rag_float_chat_messages'

interface Quota {
  remaining: number
  limit: number
  tier: string
}

function loadFloatSession(): Message[] {
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

function saveFloatSession(messages: Message[]) {
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
  const [quota, setQuota] = useState<Quota | null>(null)
  const [messageSources, setMessageSources] = useState<Record<string, ArticleSource[]>>({})

  const token = (session as any)?.accessToken as string | undefined
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId

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
        } catch {}
      }
      return openaiAdapter.parse(line)
    },
  }), [])

  const fetchQuota = useCallback(async () => {
    try {
      const res = await fetch(QUOTA_ENDPOINT, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        setQuota({ remaining: data.remaining, limit: data.limit, tier: data.tier })
      }
    } catch {}
  }, [token])

  useEffect(() => {
    if (status === 'authenticated') {
      fetchQuota()
    }
  }, [status, fetchQuota])

  const { messages, sendMessage, isLoading, clearMessages } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: customAdapter,
    initialMessages: loadFloatSession(),
    headers,
    onError: (err) => {
      const is429 = err.message.includes('429')
      const is503 = err.message.includes('503')
      if (is429) {
        toast.warning(t('rag.rateLimitError'))
        fetchQuota()
      } else if (is503) {
        toast.error(t('rag.serviceUnavailable'))
      } else {
        toast.error(t('rag.genericError'))
      }
    },
  })

  // Associate pending sources with the last assistant message when stream finishes
  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading && pendingSourcesRef.current.length > 0) {
      const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')
      if (lastAssistant) {
        setMessageSources(s => ({ ...s, [lastAssistant.id]: pendingSourcesRef.current }))
      }
      pendingSourcesRef.current = []
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, messages])

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      saveFloatSession(messages)
    }
  }, [messages])

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
      setQuota(q => q && q.remaining > 0 ? { ...q, remaining: q.remaining - 1 } : q)
    },
    [sendMessage]
  )

  const handleNewChat = useCallback(() => {
    clearMessages()
    localStorage.removeItem(FLOAT_STORAGE_KEY)
    setMessageSources({})
  }, [clearMessages])

  // Show spinner placeholder while session resolves
  if (status === 'loading') return null

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
      title={`${t('rag.assistantTitle')}${quotaSuffix}`}
      placeholder={t('rag.placeholder')}
    />
  )
}
