import type { Message } from '@s091648/chatbot-plugin-ui'

export interface ArticleSource {
  id: string
  title: string | null
  url: string
  public_article_id: string | null
  /** 1-based index of this source's [N] citation marker in the original LLM context — chat's
   * backend narrows `sources` down to only the cited articles, which can leave gaps (e.g. only
   * [1] and [3] cited out of four), so this must be used to resolve a [N] marker instead of the
   * array position. Weekly-report sources don't set this (their list is never narrowed, so
   * position already lines up with the marker) — CitedContent falls back to positional lookup
   * when it's absent. */
  number?: number
}

/** One question+answer exchange — paired up from useChat()'s flat `messages` array so
 * AnswerDisplay can page back through prior turns instead of only ever showing the latest one.
 * `assistantMessage` is undefined for the newest turn in the brief window between the question
 * being sent and the first byte of a reply coming back (see InlineQABarWrapper's `turns`
 * computation) — AnswerDisplay renders that as its own "thinking" page rather than waiting for
 * an assistant message to exist before the new turn becomes visible at all. */
export interface ConversationTurn {
  userMessage?: Message
  assistantMessage?: Message
  sources: ArticleSource[]
  /** role:'tool' messages belonging to this turn (between its user message and the next one) —
   * optional/defaults to [] so existing turn fixtures that predate tool-call display keep working. */
  toolCalls?: Message[]
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
  /** True once a turn has settled while the user was looking at an older one — mirrors the
   * weekly-report/chat card-swap unread dot. Clears itself once currentIndex reaches the
   * newest turn (via onNextTurn, or automatically when a new question is sent). */
  hasUnreadResponse: boolean
  onPrevTurn: () => void
  onNextTurn: () => void
}
