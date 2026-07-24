'use client'

import { useState, useRef, useEffect, useCallback, type KeyboardEvent, type ReactNode } from 'react'

function ThinkingBlock({ thinking, toggleLabel }: { thinking: string; toggleLabel: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mb-1 rounded-lg border border-border overflow-hidden text-xs max-w-[85%]">
      <button
        className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-left text-muted-foreground hover:bg-muted/50 transition-colors cursor-pointer"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span className={`text-[9px] transition-transform duration-150 inline-block ${open ? 'rotate-90' : ''}`}>▶</span>
        {toggleLabel}
      </button>
      {open && (
        <pre className="px-2.5 py-2 text-[11px] leading-relaxed text-muted-foreground whitespace-pre-wrap break-words border-t border-border bg-muted/30 font-sans">
          {thinking}
        </pre>
      )}
    </div>
  )
}
import type { Message } from '@s091648/chatbot-plugin-ui'
import { X, Send, SquarePen, Bot, MessageSquare, ExternalLink, Sparkles } from 'lucide-react'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailDialog } from '@/components/features/articles/article-detail-dialog'
import { useI18n } from '@/lib/providers'

export type { ArticleSource } from './types'
import type { ArticleSource } from './types'

export interface FloatingChatbotPanelProps {
  messages: Message[]
  messageSources: Record<string, ArticleSource[]>
  messageAttachments?: Record<string, Array<{ id: string; title: string }>>
  onSend: (text: string) => void
  isLoading: boolean
  onNewChat?: () => void
  onAbort?: () => void
  title?: string
  placeholder?: string
  theme?: 'light' | 'dark' | 'auto'
  open: boolean
  onOpenChange: (open: boolean) => void
  pinnedArticles?: { id: string; title: string; tags?: string[] }[]
  onRemovePinnedArticle?: (id: string) => void
}

type SourceClickFn = (src: ArticleSource) => void

function parseInline(
  text: string,
  sources?: ArticleSource[],
  onSourceClick?: SourceClickFn,
  onRefClick?: (idx: number) => void,
): ReactNode[] {
  const parts: ReactNode[] = []
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
        const linkText = text.slice(i + 1, closeBracket)
        // [text](url) markdown link
        if (text[closeBracket + 1] === '(') {
          const closeParen = text.indexOf(')', closeBracket + 2)
          if (closeParen !== -1) {
            const url = text.slice(closeBracket + 2, closeParen)
            if (/^https?:\/\//.test(url)) {
              if (buf) { parts.push(buf); buf = '' }
              parts.push(
                <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-500 underline hover:text-blue-700 dark:text-blue-400">
                  {linkText}
                </a>
              )
              i = closeParen + 1
              continue
            }
          }
        }
        // [N] citation reference
        if (/^\d+$/.test(linkText) && sources?.length) {
          const num = parseInt(linkText, 10)
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
        // [Title] citation — match against sources by title
        if (sources && sources.length > 0) {
          const lower = linkText.toLowerCase().trim()
          const matched = sources.find(s => {
            const t = (s.title ?? '').toLowerCase().trim()
            return t === lower || t.includes(lower) || lower.includes(t)
          })
          if (matched) {
            if (buf) { parts.push(buf); buf = '' }
            if (matched.public_article_id && onSourceClick) {
              parts.push(
                <button key={i} onClick={() => onSourceClick(matched)}
                  className="text-blue-500 underline hover:text-blue-700 dark:text-blue-400 cursor-pointer">
                  {linkText}
                </button>
              )
            } else {
              parts.push(
                <a key={i} href={matched.url} target="_blank" rel="noopener noreferrer"
                  className="text-blue-500 underline hover:text-blue-700 dark:text-blue-400">
                  {linkText}
                </a>
              )
            }
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

function renderMarkdown(
  text: string,
  sources?: ArticleSource[],
  onSourceClick?: SourceClickFn,
  onRefClick?: (idx: number) => void,
): ReactNode {
  const lines = text.split('\n')
  const result: ReactNode[] = []
  const listItems: string[] = []
  let key = 0

  const flush = () => {
    if (!listItems.length) return
    result.push(
      <ul key={key++} className="my-1 ml-4 list-disc space-y-0.5">
        {listItems.map((item, j) => (
          <li key={j} className="text-xs leading-relaxed">{parseInline(item, sources, onSourceClick, onRefClick)}</li>
        ))}
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
      if (t) result.push(<p key={key++} className="text-xs leading-relaxed my-0.5">{parseInline(t, sources, onSourceClick, onRefClick)}</p>)
    }
  }
  flush()
  return <>{result}</>
}

export function FloatingChatbotPanel({
  messages,
  messageSources,
  messageAttachments,
  onSend,
  isLoading,
  onNewChat,
  onAbort,
  title = 'AI Assistant',
  placeholder = 'Ask a question...',
  theme = 'auto',
  open,
  onOpenChange,
  pinnedArticles,
  onRemovePinnedArticle,
}: FloatingChatbotPanelProps) {
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const { t, locale } = useI18n()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [dialogLoading, setDialogLoading] = useState(false)
  const [dialogArticle, setDialogArticle] = useState<ArticleDetail | null>(null)
  const [highlighted, setHighlighted] = useState<{ msgId: string; idx: number } | null>(null)
  const sourceRefsMap = useRef<Map<string, (HTMLElement | null)[]>>(new Map())
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

  const handleRefClick = useCallback((msgId: string, idx: number) => {
    if (highlightTimer.current) clearTimeout(highlightTimer.current)
    setHighlighted({ msgId, idx })
    const refs = sourceRefsMap.current.get(msgId)
    refs?.[idx]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    highlightTimer.current = setTimeout(() => {
      setHighlighted(null)
      highlightTimer.current = null
    }, 2000)
  }, [])

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

  useEffect(() => {
    if (!open || !isLoading || !onAbort) return
    const handler = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') onAbort() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, isLoading, onAbort])

  const submit = () => {
    const text = input.trim()
    if (!text || isLoading) return
    onSend(text)
    setInput('')
  }

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
  }

  return (
    <div data-chatbot-theme={theme} data-testid="chatbot-plugin" className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {open && (
        <div className="w-[380px] h-[520px] flex flex-col rounded-2xl border border-border bg-card shadow-xl overflow-hidden">
          <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-card shrink-0">
            <div className="flex items-center gap-2">
              <div className="relative">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-green-500 border-2 border-card" />
              </div>
              <div>
                <div className="text-sm font-semibold leading-none" data-testid="title">{title}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{t('rag.headerStatus')}</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {onNewChat && (
                <button
                  data-testid="new-chat-btn"
                  onClick={onNewChat}
                  disabled={isLoading}
                  className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50 cursor-pointer"
                  aria-label={t('rag.newConversation')}
                >
                  <SquarePen className="h-4 w-4" />
                </button>
              )}
              <button
                onClick={() => onOpenChange(false)}
                className="p-1.5 rounded-md hover:bg-muted transition-colors cursor-pointer"
                aria-label={t('rag.closeChat')}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </header>

          <div className="themed-scrollbar flex-1 overflow-y-auto p-4 space-y-3" role="log">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                <MessageSquare className="h-8 w-8 mb-2 opacity-30" />
                <p className="text-xs">{t('rag.emptyState')}</p>
              </div>
            ) : (
              messages.map(m => (
                <div key={m.id} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {m.role !== 'user' && (
                    <span className="text-[10px] text-muted-foreground mb-1 ml-1">{t('rag.agentName')}</span>
                  )}
                  {m.role !== 'user' && m.thinking && (
                    <ThinkingBlock thinking={m.thinking} toggleLabel={t('rag.thinkingToggle')} />
                  )}
                  <div
                    className={`max-w-[85%] px-3 py-2 rounded-2xl ${
                      m.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-br-sm'
                        : 'bg-muted text-foreground rounded-bl-sm'
                    }`}
                  >
                    {m.role === 'user'
                      ? <span className="text-xs leading-relaxed">{m.content || <span className="opacity-40">…</span>}</span>
                      : (m.content ? renderMarkdown(
                          m.content,
                          messageSources[m.id],
                          (src) => src.public_article_id && openArticleDialog(src.public_article_id),
                          (idx) => handleRefClick(m.id, idx),
                        ) : <span className="text-xs opacity-40">…</span>)
                    }
                  </div>
                  {messageSources[m.id]?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1 max-w-[85%]">
                      {messageSources[m.id].map((src, idx) =>
                        src.public_article_id ? (
                          <button
                            key={src.id}
                            ref={el => {
                              if (!sourceRefsMap.current.has(m.id)) sourceRefsMap.current.set(m.id, [])
                              sourceRefsMap.current.get(m.id)![idx] = el
                            }}
                            onClick={() => openArticleDialog(src.public_article_id!)}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border text-[10px] text-muted-foreground hover:text-foreground transition-all duration-300 cursor-pointer ${
                              highlighted?.msgId === m.id && highlighted?.idx === idx
                                ? 'border-blue-500 ring-2 ring-blue-400 text-blue-600 dark:text-blue-400'
                                : 'border-border hover:border-foreground/30'
                            }`}
                          >
                            <span className="shrink-0 text-[9px] font-bold text-blue-500">{idx + 1}</span>
                            <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate max-w-[160px]">{src.title ?? src.url}</span>
                          </button>
                        ) : (
                          <a
                            key={src.id}
                            ref={el => {
                              if (!sourceRefsMap.current.has(m.id)) sourceRefsMap.current.set(m.id, [])
                              sourceRefsMap.current.get(m.id)![idx] = el as HTMLElement | null
                            }}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border text-[10px] text-muted-foreground hover:text-foreground transition-all duration-300 cursor-pointer ${
                              highlighted?.msgId === m.id && highlighted?.idx === idx
                                ? 'border-blue-500 ring-2 ring-blue-400 text-blue-600 dark:text-blue-400'
                                : 'border-border hover:border-foreground/30'
                            }`}
                          >
                            <span className="shrink-0 text-[9px] font-bold text-blue-500">{idx + 1}</span>
                            <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate max-w-[160px]">{src.title ?? src.url}</span>
                          </a>
                        )
                      )}
                    </div>
                  )}
                  {m.role === 'user' && messageAttachments?.[m.id]?.length ? (
                    <div className="mt-1.5 flex flex-wrap gap-1 max-w-[85%] justify-end">
                      {messageAttachments[m.id].map(article => (
                        <button
                          key={article.id}
                          onClick={() => openArticleDialog(article.id)}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 border border-purple-200 dark:border-purple-700 text-[10px] text-purple-700 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors cursor-pointer"
                        >
                          <Sparkles className="h-2.5 w-2.5 shrink-0" />
                          <span className="truncate max-w-[160px]">{article.title}</span>
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {m.role === 'user' && (
                    <span className="text-[10px] text-muted-foreground mt-1">
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex items-center gap-1 ml-1" aria-label={t('rag.typingAriaLabel')}>
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          <footer className="border-t border-border px-3 py-3 shrink-0 space-y-2">
            {pinnedArticles && pinnedArticles.length > 0 && (
              <div className="flex flex-wrap gap-1 px-1">
                {pinnedArticles.map(article => (
                  <div
                    key={article.id}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 border border-purple-200 dark:border-purple-700 text-[10px] text-purple-700 dark:text-purple-300"
                  >
                    <Sparkles className="h-2.5 w-2.5 shrink-0" />
                    <span className="truncate max-w-[140px]">{article.title}</span>
                    <button
                      type="button"
                      onClick={() => onRemovePinnedArticle?.(article.id)}
                      className="ml-0.5 rounded-full hover:bg-purple-200 dark:hover:bg-purple-800 transition-colors cursor-pointer shrink-0"
                      aria-label={t('rag.removeArticleRef')}
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2 bg-muted rounded-xl px-3 py-2">
              <input
                className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground/60"
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder={placeholder}
                disabled={isLoading}
                aria-label={t('rag.inputAriaLabel')}
              />
              <button
                data-testid="send-btn"
                onClick={submit}
                disabled={isLoading || !input.trim()}
                className="p-1 rounded-lg bg-primary text-primary-foreground disabled:opacity-40 transition-opacity cursor-pointer"
                aria-label={t('rag.sendAriaLabel')}
              >
                <Send className="h-3 w-3" />
              </button>
            </div>
          </footer>
        </div>
      )}

      <button
        id="tutorial-target-chat-toggle"
        onClick={() => onOpenChange(!open)}
        className="w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 transition-colors cursor-pointer"
        aria-label={open ? t('rag.closeChat') : t('rag.openChat')}
        aria-expanded={open}
      >
        {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

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
    </div>
  )
}
