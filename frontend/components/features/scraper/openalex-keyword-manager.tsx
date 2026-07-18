'use client'
import { useState } from 'react'
import { X, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/lib/providers'

interface OAKeyword { id: string; keyword: string }

export function OpenAlexKeywordManager({
  keywords,
  onAdd,
  onDelete,
}: {
  keywords: OAKeyword[]
  onAdd: (keyword: string) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [value, setValue] = useState('')
  const [adding, setAdding] = useState(false)

  async function handleAdd() {
    const trimmed = value.trim()
    if (!trimmed) return
    setAdding(true)
    await onAdd(trimmed)
    setValue('')
    setAdding(false)
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {t('admin.openAlexKeywords')}
      </p>

      <div className="flex flex-wrap gap-2 min-h-6">
        {keywords.length === 0 && (
          <p className="text-xs text-muted-foreground italic">{t('admin.noOpenAlexKeywords')}</p>
        )}
        {keywords.map(kw => (
          <span key={kw.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted text-xs">
            <span className="font-mono">{kw.keyword}</span>
            <button
              onClick={() => onDelete(kw.id)}
              className="text-muted-foreground hover:text-foreground transition-colors ml-0.5 cursor-pointer"
              aria-label={`Remove ${kw.keyword}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          className="h-9 px-3 rounded-lg border border-border bg-background text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-ring"
          placeholder={t('admin.openAlexKeywordPlaceholder')}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAdd() } }}
        />
        <Button size="sm" variant="outline" onClick={handleAdd} disabled={adding || !value.trim()}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
