'use client'

import type { Message } from '@s091648/chatbot-plugin-ui'
import { useI18n } from '@/lib/providers'

interface AnswerDisplayProps {
  messages: Message[]
  isLoading?: boolean
  error?: Error | null
}

function renderMarkdownLinks(text: string): React.ReactNode[] {
  const linkPattern = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = linkPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    parts.push(
      <a
        key={match.index}
        href={match[2]}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
      >
        {match[1]}
      </a>
    )
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts
}

export function AnswerDisplay({ messages, isLoading, error }: AnswerDisplayProps) {
  const { t } = useI18n()
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')

  if (isLoading && !lastAssistant) {
    return (
      <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm text-muted-foreground animate-pulse">
        {t('rag.thinking')}
      </div>
    )
  }

  if (error && !lastAssistant) {
    const is429 = error.message.includes('429')
    const is503 = error.message.includes('503')
    const msg = is429
      ? t('rag.rateLimitError')
      : is503
        ? t('rag.serviceUnavailable')
        : t('rag.genericError')
    return (
      <div className="mt-3 px-4 py-3 rounded-lg bg-destructive/10 text-sm text-destructive">
        {msg}
      </div>
    )
  }

  if (!lastAssistant) return null

  const lines = lastAssistant.content.split('\n')

  return (
    <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm leading-relaxed">
      {lines.map((line, i) => (
        <p key={i} className={i > 0 ? 'mt-2' : ''}>
          {renderMarkdownLinks(line)}
        </p>
      ))}
      {isLoading && (
        <span className="inline-block w-1.5 h-4 ml-0.5 bg-foreground/60 animate-pulse align-middle" />
      )}
    </div>
  )
}
