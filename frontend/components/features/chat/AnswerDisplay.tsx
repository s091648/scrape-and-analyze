'use client'

import { useCallback, useState } from 'react'
import type { Message } from '@s091648/chatbot-plugin-ui'
import { ExternalLink } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailDialog } from '@/components/features/articles/article-detail-dialog'
import type { ArticleSource } from './types'

interface AnswerDisplayProps {
  messages: Message[]
  isLoading?: boolean
  error?: Error | null
  sources?: ArticleSource[]
}

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  let i = 0
  let buf = ''

  while (i < text.length) {
    if (text[i] === '*' && text[i + 1] === '*') {
      const end = text.indexOf('**', i + 2)
      if (end !== -1) {
        if (buf) { parts.push(buf); buf = '' }
        parts.push(<strong key={i}>{text.slice(i + 2, end)}</strong>)
        i = end + 2
        continue
      }
    }
    if (text[i] === '[') {
      const closeBracket = text.indexOf(']', i + 1)
      if (closeBracket !== -1 && text[closeBracket + 1] === '(') {
        const closeParen = text.indexOf(')', closeBracket + 2)
        if (closeParen !== -1) {
          const linkText = text.slice(i + 1, closeBracket)
          const linkUrl = text.slice(closeBracket + 2, closeParen)
          if (/^https?:\/\//.test(linkUrl)) {
            if (buf) { parts.push(buf); buf = '' }
            parts.push(
              <a key={i} href={linkUrl} target="_blank" rel="noopener noreferrer"
                className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400">
                {linkText}
              </a>
            )
            i = closeParen + 1
            continue
          }
        }
      }
    }
    buf += text[i++]
  }
  if (buf) parts.push(buf)
  return parts
}

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const result: React.ReactNode[] = []
  const listItems: string[] = []
  let key = 0

  const flush = () => {
    if (!listItems.length) return
    result.push(
      <ul key={key++} className="my-1 ml-4 list-disc space-y-0.5">
        {listItems.map((item, j) => <li key={j}>{parseInline(item)}</li>)}
      </ul>
    )
    listItems.length = 0
  }

  for (const line of lines) {
    const t = line.trim()
    if (/^[*-]\s/.test(t)) {
      listItems.push(t.slice(2))
    } else {
      flush()
      if (t) result.push(<p key={key++} className={key > 1 ? 'mt-2' : ''}>{parseInline(t)}</p>)
    }
  }
  flush()
  return <>{result}</>
}

export function AnswerDisplay({ messages, isLoading, error, sources }: AnswerDisplayProps) {
  const { t, locale } = useI18n()
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [dialogArticle, setDialogArticle] = useState<ArticleDetail | null>(null)

  const openArticleDialog = useCallback(async (publicArticleId: string) => {
    setDialogOpen(true)
    setDialogLoading(true)
    setDialogArticle(null)
    try {
      const detail = await fetchArticleById(publicArticleId, locale)
      setDialogArticle(detail)
    } finally {
      setDialogLoading(false)
    }
  }, [locale])

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
      <div className="mt-3 px-4 py-3 rounded-lg bg-muted/50 text-sm leading-relaxed">
        {renderMarkdown(lastAssistant.content)}
        {isLoading && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-foreground/60 animate-pulse align-middle" />
        )}
        {!isLoading && sources && sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-border flex flex-wrap gap-1.5">
            {sources.map(src =>
              src.public_article_id ? (
                <button
                  key={src.id}
                  onClick={() => openArticleDialog(src.public_article_id!)}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                >
                  <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                  <span className="truncate max-w-[200px]">{src.title ?? src.url}</span>
                </button>
              ) : (
                <a
                  key={src.id}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border border-border text-[11px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                >
                  <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                  <span className="truncate max-w-[200px]">{src.title ?? src.url}</span>
                </a>
              )
            )}
          </div>
        )}
      </div>

      <ArticleDetailDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={dialogArticle?.title ?? ''}
        source={dialogArticle?.source ?? ''}
        url={dialogArticle?.url ?? ''}
        via_source={dialogArticle?.via_source}
        original_source={dialogArticle?.original_source}
        published_at={dialogArticle?.published_at ?? null}
        content={dialogArticle?.content ?? ''}
        detail={dialogArticle}
        loading={dialogLoading}
      />
    </>
  )
}
