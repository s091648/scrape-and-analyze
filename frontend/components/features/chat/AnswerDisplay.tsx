'use client'

import { useState } from 'react'
import type { Message } from '@s091648/chatbot-plugin-ui'
import { useI18n } from '@/lib/providers'
import { CitedContent } from './cited-content'
import type { ArticleSource } from './types'

interface AnswerDisplayProps {
  messages: Message[]
  isLoading?: boolean
  error?: Error | null
  sources?: ArticleSource[]
}

function ThinkingBlock({ thinking, toggleLabel }: { thinking: string; toggleLabel: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-3 rounded-lg border border-border overflow-hidden text-xs">
      <button
        className="flex items-center gap-1.5 w-full px-3 py-2 text-left text-muted-foreground hover:bg-muted/50 transition-colors cursor-pointer"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className={`text-[9px] transition-transform duration-150 inline-block ${open ? 'rotate-90' : ''}`}>▶</span>
        {toggleLabel}
      </button>
      {open && (
        <pre className="px-3 py-2 text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap break-words border-t border-border bg-muted/30 font-sans">
          {thinking}
        </pre>
      )}
    </div>
  )
}

export function AnswerDisplay({ messages, isLoading, error, sources }: AnswerDisplayProps) {
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

  return (
    <>
      {lastAssistant.thinking && (
        <ThinkingBlock thinking={lastAssistant.thinking} toggleLabel={t('rag.thinkingToggle')} />
      )}
      <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm leading-relaxed">
        <CitedContent text={lastAssistant.content} sources={sources} showSourceList={!isLoading} />
        {isLoading && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-foreground/60 animate-pulse align-middle" />
        )}
      </div>
    </>
  )
}
