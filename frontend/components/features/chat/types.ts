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
