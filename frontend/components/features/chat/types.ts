import type { Message } from '@s091648/chatbot-plugin-ui'

export interface ArticleSource {
  id: string
  title: string | null
  url: string
  public_article_id: string | null
}

/** One settled question+answer exchange — paired up from useChat()'s flat `messages` array so
 * AnswerDisplay can page back through prior turns instead of only ever showing the latest one. */
export interface ConversationTurn {
  userMessage?: Message
  assistantMessage: Message
  sources: ArticleSource[]
}

/** Everything AnswerDisplay needs, reported upward by InlineQABarWrapper (which owns the actual
 * useChat() state) via an onConversationChange callback — not a Context, because the wrapper's
 * input bar and the answer panel that shows this state are siblings rendered by their common
 * parent (WeeklyReportWidget), not nested inside each other; a Context.Provider rendered by
 * InlineQABarWrapper would only wrap its own subtree and never actually reach a sibling. */
export interface ChatConversationSnapshot {
  turns: ConversationTurn[]
  currentIndex: number
  isLoading: boolean
  error: Error | null
  onPrevTurn: () => void
  onNextTurn: () => void
}
