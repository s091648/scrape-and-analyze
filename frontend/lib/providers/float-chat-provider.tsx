'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { openaiAdapter, useChat, type StreamAdapter, type StreamEvent, type Message } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n } from './i18n-provider'
import { useTopic } from './topic-provider'
import { useAuthToken } from './auth-token-provider'
import { useChatQuota } from './chat-quota-provider'
import { usePinnedArticle, type PinnedArticle } from './pinned-article-provider'
import { loadChatMessages, saveChatMessages } from '@/lib/chat/chat-storage'
import type { ArticleSource } from '@/components/features/chat/types'

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'
const FLOAT_STORAGE_KEY = 'rag_float_chat_messages'

interface FloatChatContextValue {
  messages: Message[]
  messageSources: Record<string, ArticleSource[]>
  messageAttachments: Record<string, PinnedArticle[]>
  isLoading: boolean
  chatOpen: boolean
  setChatOpen: (open: boolean) => void
  onSend: (text: string) => void
  onNewChat: () => void
  onAbort: () => void
}

const FloatChatContext = createContext<FloatChatContextValue | null>(null)

/** Owns the floating chatbot's useChat() session at the app root (see lib/providers/index.tsx)
 * so it survives FloatingChatbotWrapper mounting/unmounting as the user navigates between
 * isChatPath and non-chat routes — an in-flight stream keeps running and updating this state
 * even while no component is currently rendering it, instead of being silently abandoned. */
export function FloatChatProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const { selectedTopicId } = useTopic()
  const { t } = useI18n()
  const { refreshQuota } = useChatQuota()
  const { pinnedArticles, clearPinnedArticles } = usePinnedArticle()

  const [messageSources, setMessageSources] = useState<Record<string, ArticleSource[]>>({})
  const [messageAttachments, setMessageAttachments] = useState<Record<string, PinnedArticle[]>>({})
  const [chatOpen, setChatOpen] = useState(false)
  const prevPinnedCountRef = useRef(0)
  const pendingPinnedRef = useRef<PinnedArticle[]>([])
  const prevUserMsgCountRef = useRef(0)

  const { token } = useAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId
  if (pinnedArticles.length > 0) headers['X-Pinned-Article-Ids'] = pinnedArticles.map(a => a.id).join(',')

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

  // Bumped by onNewChat to force a real reset — see the effect below for why a plain
  // clearMessages() call in the click handler isn't enough on its own.
  const [resetToken, setResetToken] = useState(0)

  // Re-evaluated when userId OR resetToken changes. userId-change is what lets the effect below
  // swap sessions (no more userId-keyed `key` remount now that this provider is mounted once at
  // the app root); resetToken is what lets onNewChat force a *fresh* empty snapshot — without it,
  // this memo would stay frozen at whatever was loaded on first mount forever, since nothing else
  // ever changes after that first render.
  const initialMessages = useMemo(
    () => loadChatMessages('local', FLOAT_STORAGE_KEY, userId),
    [userId, resetToken]
  )

  const { messages, sendMessage, isLoading, clearMessages, abort } = useChat({
    endpoint: CHAT_ENDPOINT,
    streamAdapter: customAdapter,
    initialMessages,
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

  // clearMessages() (from useChat) resets `messages` to whatever `initialMessages` equals on
  // THIS render — so it must run in an effect keyed on initialMessages/clearMessages themselves,
  // never synchronously inside the click handler that triggered the change. userId and
  // resetToken both recompute `initialMessages` synchronously during the same render that
  // changes them, so by the time this effect runs post-commit, clearMessages() is guaranteed to
  // target the fresh value — calling it eagerly inside onSession-change logic or onNewChat
  // itself would instead capture the *previous* render's stale closure and appear to do nothing
  // (this was the pencil-icon "New Chat" bug: it reset messages back to themselves).
  const prevResetKeyRef = useRef(`${userId}:${resetToken}`)
  useEffect(() => {
    const key = `${userId}:${resetToken}`
    if (prevResetKeyRef.current !== key) {
      clearMessages()
      setMessageSources({})
      setMessageAttachments({})
      pendingPinnedRef.current = []
      prevUserMsgCountRef.current = 0
      prevResetKeyRef.current = key
    }
  }, [userId, resetToken, clearMessages])

  // Clear storage on logout so the next user starts fresh (belt-and-suspenders alongside the
  // userId check in loadChatMessages, which already refuses to load another user's history).
  useEffect(() => {
    if (status === 'unauthenticated' && typeof window !== 'undefined') {
      localStorage.removeItem(FLOAT_STORAGE_KEY)
    }
  }, [status])

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
  }, [isLoading, messages, refreshQuota, t])

  // Persist messages to localStorage, tagged with current userId
  useEffect(() => {
    if (messages.length > 0) {
      saveChatMessages('local', FLOAT_STORAGE_KEY, userId, messages)
    }
  }, [messages, userId])

  // Auto-open only when an article is added (count increases), not on removal
  useEffect(() => {
    if (pinnedArticles.length > prevPinnedCountRef.current) setChatOpen(true)
    prevPinnedCountRef.current = pinnedArticles.length
  }, [pinnedArticles.length])

  // When a new user message appears, attach the pending pinned articles snapshot to it
  useEffect(() => {
    const userMessages = messages.filter(m => m.role === 'user')
    if (userMessages.length > prevUserMsgCountRef.current && pendingPinnedRef.current.length > 0) {
      const lastUser = userMessages[userMessages.length - 1]
      const snapshot = pendingPinnedRef.current
      pendingPinnedRef.current = []
      setMessageAttachments(prev => ({ ...prev, [lastUser.id]: snapshot }))
    }
    prevUserMsgCountRef.current = userMessages.length
  }, [messages])

  const onSend = useCallback(
    (text: string) => {
      if (!text.trim()) return
      if (pinnedArticles.length > 0) pendingPinnedRef.current = [...pinnedArticles]
      sendMessage(text)
    },
    [sendMessage, pinnedArticles]
  )

  const onNewChat = useCallback(() => {
    if (typeof window !== 'undefined') localStorage.removeItem(FLOAT_STORAGE_KEY)
    // Bumping resetToken (rather than calling clearMessages() here directly) is what makes this
    // work when there's existing history — see the effect above.
    setResetToken(t => t + 1)
    clearPinnedArticles()
  }, [clearPinnedArticles])

  const value = useMemo((): FloatChatContextValue => ({
    messages,
    messageSources,
    messageAttachments,
    isLoading,
    chatOpen,
    setChatOpen,
    onSend,
    onNewChat,
    onAbort: abort,
  }), [messages, messageSources, messageAttachments, isLoading, chatOpen, onSend, onNewChat, abort])

  return <FloatChatContext.Provider value={value}>{children}</FloatChatContext.Provider>
}

export function useFloatChat() {
  const ctx = useContext(FloatChatContext)
  if (!ctx) throw new Error('useFloatChat must be used within FloatChatProvider')
  return ctx
}
