'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { openaiAdapter, useChat, type StreamAdapter, type StreamEvent, type Message } from '@s091648/chatbot-plugin-ui'
import { toast } from 'sonner'
import { useI18n } from './i18n-provider'
import { useTopic } from './topic-provider'
import { useAuthToken } from './auth-token-provider'
import { useChatQuota } from './chat-quota-provider'
import { usePinnedReport } from './pinned-article-provider'
import { loadChatMessages, saveChatMessages } from '@/lib/chat/chat-storage'
import type { ArticleSource, ConversationTurn } from '@/components/features/chat/types'

const CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT || '/api/proxy/chat/completions'
const INLINE_STORAGE_KEY = 'rag_inline_chat_messages'

interface InlineChatContextValue {
  messages: Message[]
  turns: ConversationTurn[]
  currentTurnIndex: number
  isLoading: boolean
  error: Error | null
  hasUnreadResponse: boolean
  onPrevTurn: () => void
  onNextTurn: () => void
  onSend: (text: string) => void
  onAbort: () => void
}

const InlineChatContext = createContext<InlineChatContextValue | null>(null)

/** Owns the weekly-report inline chat's useChat() session at the app root (see
 * lib/providers/index.tsx) so it survives InlineQABarWrapper mounting/unmounting as the user
 * navigates away from and back to `/` — an in-flight stream keeps running and updating this
 * state even while no component is currently rendering it, instead of being silently abandoned.
 * Persisted to sessionStorage (not localStorage, unlike the floating chat — see
 * FloatChatProvider) per the tab-scoped-only lifetime this conversation is meant to have. */
export function InlineChatProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const { selectedTopicId } = useTopic()
  const { t } = useI18n()
  const { refreshQuota } = useChatQuota()
  const { pinnedArticles } = usePinnedReport()

  const { token } = useAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (selectedTopicId) headers['X-Topic-Id'] = selectedTopicId
  if (pinnedArticles.length > 0) headers['X-Pinned-Article-Ids'] = pinnedArticles.map(a => a.id).join(',')

  // 'guest' for unauthenticated; actual user id for authenticated
  const userId = status === 'authenticated'
    ? (((session?.user as any)?.id as string) ?? 'guest')
    : 'guest'

  const pendingSourcesRef = useRef<ArticleSource[]>([])
  const prevIsLoadingRef = useRef(false)
  // Sources for every settled turn, keyed by that turn's assistant message id — unlike a single
  // "latest sources" value, this survives paging back to an earlier turn (see ConversationTurn).
  const [sourcesByMessageId, setSourcesByMessageId] = useState<Record<string, ArticleSource[]>>({})
  const [currentTurnIndex, setCurrentTurnIndex] = useState(0)
  // True once a turn has settled while the user was looking at an older one — see
  // ChatConversationSnapshot.hasUnreadResponse.
  const [hasUnreadResponse, setHasUnreadResponse] = useState(false)

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

  const initialMessages = useMemo(
    () => loadChatMessages('session', INLINE_STORAGE_KEY, userId),
    [userId]
  )

  const { messages, sendMessage, isLoading, error, clearMessages, abort } = useChat({
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

  // This provider is mounted once at the app root and never remounts — see the matching effect
  // in FloatChatProvider for why an explicit userId-change reset is needed here instead.
  const prevUserIdRef = useRef(userId)
  useEffect(() => {
    if (prevUserIdRef.current !== userId) {
      clearMessages()
      setSourcesByMessageId({})
      setCurrentTurnIndex(0)
      setHasUnreadResponse(false)
      prevUserIdRef.current = userId
    }
  }, [userId, clearMessages])

  useEffect(() => {
    if (status === 'unauthenticated' && typeof window !== 'undefined') {
      sessionStorage.removeItem(INLINE_STORAGE_KEY)
    }
  }, [status])

  // Every user/assistant message pair, oldest first — lets AnswerDisplay page back through
  // settled turns instead of only ever showing the latest one. The still-streaming message (if
  // any) falls back to pendingSourcesRef directly: sourcesByMessageId only gets a message's
  // entry once its response fully settles, but the backend sends sources early in the stream
  // (retrieval happens before generation), so inline [N] citations can — and should — already be
  // clickable while the answer is still typing in, not just after it finishes.
  const turns = useMemo((): ConversationTurn[] => {
    const result: ConversationTurn[] = []
    let pendingUser: typeof messages[number] | undefined
    // useChat pushes the assistant placeholder immediately after the user message, then appends
    // role:'tool' messages AFTER it as they arrive during streaming — so a turn's tool calls
    // physically sit *after* its assistant message in the array, not before. Pushing this same
    // array reference into the turn object at assistant-push time, and continuing to .push() into
    // it (without ever reassigning it) until the next user message starts a new turn, means later
    // tool messages land in the already-pushed turn's `toolCalls` too, via the shared reference —
    // this only needs to be correct within this one pass, since `turns` recomputes fully from
    // `messages` on every change (see the deps array below).
    let pendingToolCalls: typeof messages = []
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i]
      if (m.role === 'user') {
        pendingUser = m
        pendingToolCalls = []
      } else if (m.role === 'tool') {
        pendingToolCalls.push(m)
      } else if (m.role === 'assistant') {
        const isLiveMessage = isLoading && i === messages.length - 1
        const sources = sourcesByMessageId[m.id] ?? (isLiveMessage ? pendingSourcesRef.current : [])
        result.push({ userMessage: pendingUser, assistantMessage: m, sources, toolCalls: pendingToolCalls })
        pendingUser = undefined
      }
    }
    // A question was just sent but no reply has come back at all yet (useChat only adds the
    // assistant message once its fetch() resolves) — surface it as its own turn right away so
    // the view switches to a "thinking" page the moment the user asks, instead of only once
    // the first byte of a reply arrives.
    if (pendingUser) {
      result.push({ userMessage: pendingUser, assistantMessage: undefined, sources: [], toolCalls: pendingToolCalls })
    }
    return result
  }, [messages, sourcesByMessageId, isLoading])

  useEffect(() => {
    if (prevIsLoadingRef.current && !isLoading) {
      // Capture BEFORE clearing — the functional updater passed to setSourcesByMessageId runs
      // during the next render, by which point pendingSourcesRef.current would already be [] if
      // we cleared it first. Same fix applied in FloatChatProvider.
      const captured = pendingSourcesRef.current
      pendingSourcesRef.current = []
      const justFinished = [...messages].reverse().find(m => m.role === 'assistant')
      if (justFinished && captured.length > 0) {
        setSourcesByMessageId(prev => ({ ...prev, [justFinished.id]: captured }))
      }
      // The turn that just settled is always the newest one — if the user had navigated away
      // to an older turn while it was streaming, flag it unread (mirrors the weekly-report ↔
      // chat card-swap red dot in weekly-report-widget.tsx).
      if (currentTurnIndex !== turns.length - 1) {
        setHasUnreadResponse(true)
      }
      refreshQuota()
    }
    prevIsLoadingRef.current = isLoading
  }, [isLoading, messages, refreshQuota, currentTurnIndex, turns.length])

  // Persist messages to sessionStorage, tagged with current userId
  useEffect(() => {
    if (messages.length > 0) {
      saveChatMessages('session', INLINE_STORAGE_KEY, userId, messages)
    }
  }, [messages, userId])

  // A newly-asked question always becomes the visible one — jumping back to an older turn is a
  // manual, temporary detour, not a state that should survive the next question being asked.
  useEffect(() => {
    setCurrentTurnIndex(Math.max(0, turns.length - 1))
  }, [turns.length])

  // "Read" = looking at the newest turn — clears the flag whether the user paged forward
  // manually or a new question's auto-advance (above) landed them there.
  useEffect(() => {
    if (hasUnreadResponse && currentTurnIndex === turns.length - 1) {
      setHasUnreadResponse(false)
    }
  }, [currentTurnIndex, turns.length, hasUnreadResponse])

  const onSend = useCallback((text: string) => {
    if (!text.trim()) return
    sendMessage(text)
  }, [sendMessage])

  const onPrevTurn = useCallback(() => setCurrentTurnIndex(i => Math.max(0, i - 1)), [])
  const onNextTurn = useCallback(
    () => setCurrentTurnIndex(i => Math.min(turns.length - 1, i + 1)),
    [turns.length]
  )

  const value = useMemo((): InlineChatContextValue => ({
    messages,
    turns,
    currentTurnIndex,
    isLoading,
    error,
    hasUnreadResponse,
    onPrevTurn,
    onNextTurn,
    onSend,
    onAbort: abort,
  }), [messages, turns, currentTurnIndex, isLoading, error, hasUnreadResponse, onPrevTurn, onNextTurn, onSend, abort])

  return <InlineChatContext.Provider value={value}>{children}</InlineChatContext.Provider>
}

export function useInlineChat() {
  const ctx = useContext(InlineChatContext)
  if (!ctx) throw new Error('useInlineChat must be used within InlineChatProvider')
  return ctx
}
