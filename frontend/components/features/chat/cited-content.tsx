'use client'
import { useCallback, useRef, useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { useI18n } from '@/lib/providers'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailDialog } from '@/components/features/articles/article-detail-dialog'
import type { ArticleSource } from './types'

interface CitedContentProps {
  text: string
  sources?: ArticleSource[]
  /** Hide the trailing source-chip row (e.g. while a chat response is still streaming). Inline [N] markers still link. */
  showSourceList?: boolean
}

export function parseInline(
  text: string,
  sources?: ArticleSource[],
  onRefClick?: (idx: number) => void,
): React.ReactNode[] {
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
      if (closeBracket !== -1) {
        const inner = text.slice(i + 1, closeBracket)
        // [text](url) markdown link
        if (text[closeBracket + 1] === '(') {
          const closeParen = text.indexOf(')', closeBracket + 2)
          if (closeParen !== -1) {
            const linkUrl = text.slice(closeBracket + 2, closeParen)
            if (/^https?:\/\//.test(linkUrl)) {
              if (buf) { parts.push(buf); buf = '' }
              parts.push(
                <a key={i} href={linkUrl} target="_blank" rel="noopener noreferrer"
                  className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400">
                  {inner}
                </a>
              )
              i = closeParen + 1
              continue
            }
          }
        }
        // [N] citation reference
        if (/^\d+$/.test(inner) && sources?.length) {
          const num = parseInt(inner, 10)
          if (num >= 1 && num <= sources.length) {
            const src = sources[num - 1]
            if (buf) { parts.push(buf); buf = '' }
            parts.push(
              <button
                key={i}
                onClick={() => onRefClick?.(num - 1)}
                title={src.title ?? src.url}
                className="inline-flex items-center justify-center min-w-[1.1rem] h-[1.1rem] rounded-full bg-blue-100 text-blue-600 text-[9px] font-bold hover:bg-blue-200 dark:bg-blue-900/50 dark:text-blue-400 mx-0.5 align-middle cursor-pointer"
              >
                {num}
              </button>
            )
            i = closeBracket + 1
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

export function renderMarkdown(
  text: string,
  sources?: ArticleSource[],
  onRefClick?: (idx: number) => void,
): React.ReactNode {
  const lines = text.split('\n')
  const result: React.ReactNode[] = []
  const listItems: string[] = []
  let key = 0

  const flush = () => {
    if (!listItems.length) return
    result.push(
      <ul key={key++} className="my-1 ml-4 list-disc space-y-0.5">
        {listItems.map((item, j) => <li key={j}>{parseInline(item, sources, onRefClick)}</li>)}
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
      if (t) result.push(<p key={key++} className={key > 1 ? 'mt-2' : ''}>{parseInline(t, sources, onRefClick)}</p>)
    }
  }
  flush()
  return <>{result}</>
}

export function CitedContent({ text, sources, showSourceList = true }: CitedContentProps) {
  const { locale } = useI18n()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [dialogArticle, setDialogArticle] = useState<ArticleDetail | null>(null)
  const [highlightedSrcIdx, setHighlightedSrcIdx] = useState<number | null>(null)
  const sourceRefs = useRef<(HTMLElement | null)[]>([])
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  const handleRefClick = useCallback((idx: number) => {
    if (highlightTimer.current) clearTimeout(highlightTimer.current)
    setHighlightedSrcIdx(idx)
    sourceRefs.current[idx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    highlightTimer.current = setTimeout(() => {
      setHighlightedSrcIdx(null)
      highlightTimer.current = null
    }, 2000)
  }, [])

  return (
    <>
      {renderMarkdown(text, sources, handleRefClick)}
      {showSourceList && sources && sources.length > 0 && (
        <div className="mt-3 pt-2 border-t border-border flex flex-wrap gap-1.5">
          {sources.map((src, idx) =>
            src.public_article_id ? (
              <button
                key={src.id}
                ref={el => { sourceRefs.current[idx] = el }}
                onClick={() => openArticleDialog(src.public_article_id!)}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border text-[11px] text-muted-foreground hover:text-foreground transition-all duration-300 cursor-pointer ${
                  highlightedSrcIdx === idx
                    ? 'border-blue-500 ring-2 ring-blue-400 text-blue-600 dark:text-blue-400'
                    : 'border-border hover:border-foreground/30'
                }`}
              >
                <span className="shrink-0 text-[10px] font-bold text-blue-500">{idx + 1}</span>
                <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                <span className="truncate max-w-[200px]">{src.title ?? src.url}</span>
              </button>
            ) : (
              <a
                key={src.id}
                ref={el => { sourceRefs.current[idx] = el as HTMLElement | null }}
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border text-[11px] text-muted-foreground hover:text-foreground transition-all duration-300 cursor-pointer ${
                  highlightedSrcIdx === idx
                    ? 'border-blue-500 ring-2 ring-blue-400 text-blue-600 dark:text-blue-400'
                    : 'border-border hover:border-foreground/30'
                }`}
              >
                <span className="shrink-0 text-[10px] font-bold text-blue-500">{idx + 1}</span>
                <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                <span className="truncate max-w-[200px]">{src.title ?? src.url}</span>
              </a>
            )
          )}
        </div>
      )}

      <ArticleDetailDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        id={dialogArticle?.id ?? ''}
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
