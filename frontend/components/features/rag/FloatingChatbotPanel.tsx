'use client'

import { useState, useRef, useEffect, useCallback, type KeyboardEvent, type ReactNode } from 'react'
import type { Message } from '@s091648/chatbot-plugin-ui'
import { X, Send, SquarePen, Bot, MessageSquare, ExternalLink } from 'lucide-react'
import { fetchArticleById, type ArticleDetail } from '@/lib/api/articles'
import { ArticleDetailDialog } from '@/components/features/articles/article-detail-dialog'
import { useI18n } from '@/lib/providers'

export interface ArticleSource {
  id: string
  title: string | null
  url: string
  public_article_id: string | null
}

export interface FloatingChatbotPanelProps {
  messages: Message[]
  messageSources: Record<string, ArticleSource[]>
  onSend: (text: string) => void
  isLoading: boolean
  onNewChat?: () => void
  title?: string
  placeholder?: string
  theme?: 'light' | 'dark' | 'auto'
}

function parseInline(text: string): ReactNode[] {
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
    buf += text[i++]
  }
  if (buf) parts.push(buf)
  return parts
}

function renderMarkdown(text: string): ReactNode {
  const lines = text.split('\n')
  const result: ReactNode[] = []
  const listItems: string[] = []
  let key = 0

  const flush = () => {
    if (!listItems.length) return
    result.push(
      <ul key={key++} className="my-1 ml-4 list-disc space-y-0.5">
        {listItems.map((item, j) => (
          <li key={j} className="text-xs leading-relaxed">{parseInline(item)}</li>
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
      if (t) result.push(<p key={key++} className="text-xs leading-relaxed my-0.5">{parseInline(t)}</p>)
    }
  }
  flush()
  return <>{result}</>
}

export function FloatingChatbotPanel({
  messages,
  messageSources,
  onSend,
  isLoading,
  onNewChat,
  title = 'AI Assistant',
  placeholder = 'Ask a question...',
  theme = 'auto',
}: FloatingChatbotPanelProps) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const { locale } = useI18n()
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

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, open])

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
                <div className="text-[10px] text-muted-foreground mt-0.5">Online</div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {onNewChat && (
                <button
                  data-testid="new-chat-btn"
                  onClick={onNewChat}
                  disabled={isLoading}
                  className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
                  aria-label="New conversation"
                >
                  <SquarePen className="h-4 w-4" />
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md hover:bg-muted transition-colors"
                aria-label="Close chat"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto p-4 space-y-3" role="log">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
                <MessageSquare className="h-8 w-8 mb-2 opacity-30" />
                <p className="text-xs">Start a conversation.</p>
              </div>
            ) : (
              messages.map(m => (
                <div key={m.id} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {m.role !== 'user' && (
                    <span className="text-[10px] text-muted-foreground mb-1 ml-1">Agent</span>
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
                      : (m.content ? renderMarkdown(m.content) : <span className="text-xs opacity-40">…</span>)
                    }
                  </div>
                  {messageSources[m.id]?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1 max-w-[85%]">
                      {messageSources[m.id].map(src =>
                        src.public_article_id ? (
                          <button
                            key={src.id}
                            onClick={() => openArticleDialog(src.public_article_id!)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border border-border text-[10px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                          >
                            <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate max-w-[160px]">{src.title ?? src.url}</span>
                          </button>
                        ) : (
                          <a
                            key={src.id}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-background border border-border text-[10px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
                          >
                            <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate max-w-[160px]">{src.title ?? src.url}</span>
                          </a>
                        )
                      )}
                    </div>
                  )}
                  {m.role === 'user' && (
                    <span className="text-[10px] text-muted-foreground mt-1">
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex items-center gap-1 ml-1" aria-label="Agent is typing">
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

          <footer className="border-t border-border px-3 py-3 shrink-0">
            <div className="flex items-center gap-2 bg-muted rounded-xl px-3 py-2">
              <input
                className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground/60"
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKey}
                placeholder={placeholder}
                disabled={isLoading}
                aria-label="Type a message"
              />
              <button
                data-testid="send-btn"
                onClick={submit}
                disabled={isLoading || !input.trim()}
                className="p-1 rounded-lg bg-primary text-primary-foreground disabled:opacity-40 transition-opacity"
                aria-label="Send message"
              >
                <Send className="h-3 w-3" />
              </button>
            </div>
          </footer>
        </div>
      )}

      <button
        onClick={() => setOpen(v => !v)}
        className="w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 transition-colors"
        aria-label={open ? 'Close chat' : 'Open chat'}
        aria-expanded={open}
      >
        {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

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
    </div>
  )
}
