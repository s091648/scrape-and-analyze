'use client'

import { useSession } from 'next-auth/react'
import { useI18n, useTheme, useGuestMode, useChatQuota, usePinnedArticle, useFloatChat } from '@/lib/providers'
import { FloatingChatbotPanel } from './FloatingChatbotPanel'

export function FloatingChatbotWrapper() {
  const { status } = useSession()
  const { t } = useI18n()
  const { mode } = useTheme()
  const { isGuestMode } = useGuestMode()
  const { quota } = useChatQuota()
  const { pinnedArticles, removePinnedArticle } = usePinnedArticle()
  const {
    messages,
    messageSources,
    messageAttachments,
    isLoading,
    chatOpen,
    setChatOpen,
    onSend,
    onNewChat,
    onAbort,
  } = useFloatChat()

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
      messageAttachments={messageAttachments}
      onSend={onSend}
      isLoading={isLoading}
      onNewChat={onNewChat}
      onAbort={onAbort}
      title={`${t('rag.assistantTitle')}${quotaSuffix}`}
      placeholder={t('rag.placeholder')}
      open={chatOpen}
      onOpenChange={setChatOpen}
      pinnedArticles={pinnedArticles}
      onRemovePinnedArticle={removePinnedArticle}
    />
  )
}
