'use client'
import { useState, useEffect } from 'react'
import { Pencil, X, Check, Plus } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { useI18n } from '@/lib/providers'

export interface ScraperSetting {
  id: string
  source_type: 'rss' | 'blog' | 'arxiv'
  name: string
  url: string
  frequency: number
  is_active: boolean
  selector_config?: Record<string, unknown> | null
  last_scraped_at?: string | null
  activity?: number[] // 14 values oldest→newest (one per day)
}

export interface RssKeyword {
  id: string
  keyword: string
}

export function formatFrequency(hours: number): string {
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  const rem = hours % 24
  return rem > 0 ? `${hours}h (= ${days}d ${rem}h)` : `${hours}h (= ${days}d)`
}

// Scheduler runs daily at 08:00 UTC.
const SCHEDULER_HOUR_UTC = 8

function msUntilNextScheduledRun(): number {
  const now = Date.now()
  const d = new Date(now)
  const todayRun = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), SCHEDULER_HOUR_UTC)
  if (todayRun > now) return todayRun - now
  const tomorrowRun = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1, SCHEDULER_HOUR_UTC)
  return tomorrowRun - now
}

// Matches the SQL early-trigger window: sources are picked up 30 min before
// their nominal due time so a source scraped just after the run is still
// caught at the *next* scheduled run rather than having to wait a full extra day.
const EARLY_WINDOW_MS = 30 * 60 * 1000

function msUntilNextScrape(lastScrapedAt: string | null | undefined, frequencyHours: number): number {
  if (!lastScrapedAt) return msUntilNextScheduledRun()

  // Subtract the early window so this matches get_sources_due()'s SQL condition.
  const nextDueMs = new Date(lastScrapedAt).getTime() + frequencyHours * 3600 * 1000 - EARLY_WINDOW_MS
  if (nextDueMs <= Date.now()) return msUntilNextScheduledRun()

  // Find the next 08:00 UTC *on or after* nextDueMs.
  const d = new Date(nextDueMs)
  const sameDay08 = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), SCHEDULER_HOUR_UTC)
  const nextScrapeMs = nextDueMs <= sameDay08
    ? sameDay08
    : Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1, SCHEDULER_HOUR_UTC)
  return Math.max(0, nextScrapeMs - Date.now())
}

export function formatCountdown(ms: number): string {
  if (ms <= 0) return 'due now'
  const s = Math.floor(ms / 1000)
  const days = Math.floor(s / 86400)
  const hours = Math.floor((s % 86400) / 3600)
  const mins = Math.floor((s % 3600) / 60)
  const secs = s % 60
  const hms = `${hours}h:${String(mins).padStart(2, '0')}m:${String(secs).padStart(2, '0')}s`
  return days > 0 ? `${days}d ${hms}` : hms
}

export function useNextScrapeCountdown(
  lastScrapedAt?: string | null,
  frequencyHours?: number,
): string {
  const [ms, setMs] = useState(() => msUntilNextScrape(lastScrapedAt, frequencyHours ?? 24))
  useEffect(() => {
    const id = setInterval(
      () => setMs(msUntilNextScrape(lastScrapedAt, frequencyHours ?? 24)),
      1000,
    )
    return () => clearInterval(id)
  }, [lastScrapedAt, frequencyHours])
  return formatCountdown(ms)
}

// ── Glowing status dot ────────────────────────────────────────────────────────

export function GlowDot({ active }: { active: boolean }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span
        className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
          active ? 'bg-green-400' : 'bg-red-400'
        }`}
      />
      <span
        className={`relative inline-flex rounded-full h-2 w-2 ${
          active ? 'bg-green-500' : 'bg-red-500'
        }`}
      />
    </span>
  )
}

// ── Activity graph ────────────────────────────────────────────────────────────

export function ActivityGraph({ activity }: { activity?: number[] }) {
  const data = activity && activity.length === 14 ? activity : Array(14).fill(0)
  const max = Math.max(...data, 1)

  return (
    <div className="flex gap-0.5 items-end h-6" title="Article activity – last 14 days">
      {data.map((count, i) => {
        const ratio = count / max
        const height = count === 0 ? 3 : Math.max(5, Math.round(ratio * 24))
        const opacity = count === 0 ? 0.12 : 0.25 + ratio * 0.75
        return (
          <div
            key={i}
            title={`${count} article${count !== 1 ? 's' : ''}`}
            className="w-2.5 rounded-sm"
            style={{
              height: `${height}px`,
              backgroundColor: `rgba(34,197,94,${opacity})`,
            }}
          />
        )
      })}
    </div>
  )
}

// ── Active/inactive badge (clickable toggle) ──────────────────────────────────

export function ActiveBadge({
  active,
  onToggle,
}: {
  active: boolean
  onToggle: () => void
}) {
  const { t } = useI18n()
  return (
    <button
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
        active
          ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100 dark:bg-green-950 dark:border-green-800 dark:text-green-400'
          : 'bg-red-50 border-red-200 text-red-700 hover:bg-red-100 dark:bg-red-950 dark:border-red-800 dark:text-red-400'
      }`}
    >
      <GlowDot active={active} />
      {active ? t('admin.active') : t('admin.inactive')}
    </button>
  )
}

// ── Shared form field styles ──────────────────────────────────────────────────

const inputClass =
  'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

// ── RssKeywordManager ─────────────────────────────────────────────────────────

export function RssKeywordManager({
  keywords,
  onAdd,
  onDelete,
}: {
  keywords: RssKeyword[]
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
        {t('admin.keywords')}
        <span className="ml-1 font-normal normal-case">— {t('admin.rssKeywordsOrDesc')}</span>
      </p>

      <div className="flex flex-wrap gap-2 min-h-6">
        {keywords.length === 0 && (
          <p className="text-xs text-muted-foreground italic">{t('admin.noRssKeywords')}</p>
        )}
        {keywords.map(kw => (
          <span key={kw.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-muted text-xs font-mono">
            {kw.keyword}
            <button
              onClick={() => onDelete(kw.id)}
              className="text-muted-foreground hover:text-foreground transition-colors ml-0.5"
              aria-label={`Remove ${kw.keyword}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          className="h-9 px-3 rounded-lg border border-border bg-background text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-ring font-mono"
          placeholder="e.g. digital.twin"
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

// ── SourceCard ────────────────────────────────────────────────────────────────

export function SourceCard({
  setting,
  onUpdate,
  onDelete,
  rssKeywords,
  onAddRssKeyword,
  onDeleteRssKeyword,
}: {
  setting: ScraperSetting
  onUpdate: (id: string, data: Partial<ScraperSetting>) => Promise<void>
  onDelete: (id: string) => Promise<void>
  rssKeywords?: RssKeyword[]
  onAddRssKeyword?: (keyword: string) => Promise<void>
  onDeleteRssKeyword?: (id: string) => Promise<void>
}) {
  const { t } = useI18n()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const blogCfg = setting.selector_config as { article_link?: string; title?: string; content?: string } | null
  const [form, setForm] = useState({
    name: setting.name,
    url: setting.url,
    frequency: setting.frequency,
    is_active: setting.is_active,
    selector_config: {
      article_link: blogCfg?.article_link ?? '',
      title: blogCfg?.title ?? '',
      content: blogCfg?.content ?? '',
    },
  })
  const [saving, setSaving] = useState(false)
  const countdown = useNextScrapeCountdown(setting.last_scraped_at, setting.frequency)

  async function handleSave() {
    setSaving(true)
    const payload: Partial<ScraperSetting> = {
      name: form.name,
      url: form.url,
      frequency: form.frequency,
      is_active: form.is_active,
    }
    if (setting.source_type === 'blog') payload.selector_config = form.selector_config
    await onUpdate(setting.id, payload)
    setSaving(false)
    setEditing(false)
  }

  const isRss = setting.source_type === 'rss'

  // ── Edit mode ───────────────────────────────────────────────────────────────
  if (editing) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{t('admin.editSource')}</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-3">
          <div>
            <label className={labelClass}>{t('admin.name')}</label>
            <input
              className={inputClass}
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelClass}>{t('admin.url')}</label>
            <input
              className={inputClass}
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              placeholder="https://..."
            />
          </div>
          <div>
            <label className={labelClass}>{t('admin.frequencyHours')}</label>
            <input
              type="number"
              min={1}
              className={inputClass}
              value={form.frequency}
              onChange={e => setForm(f => ({ ...f, frequency: Number(e.target.value) }))}
            />
            {form.frequency >= 24 && (
              <p className="text-xs text-muted-foreground mt-1">{formatFrequency(form.frequency)}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={form.is_active}
              onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))}
            />
            <span className="text-sm text-muted-foreground">{t('admin.active')}</span>
          </div>

          {setting.source_type === 'blog' && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {t('admin.cssSelectors')}
              </p>
              {(['article_link', 'title', 'content'] as const).map(key => (
                <div key={key}>
                  <label className={labelClass}>{key.replace('_', ' ')}</label>
                  <input
                    className={inputClass}
                    value={form.selector_config[key]}
                    placeholder={
                      key === 'article_link'
                        ? 'a.post-link'
                        : key === 'title'
                        ? 'h1.post-title'
                        : '.post-content'
                    }
                    onChange={e =>
                      setForm(f => ({
                        ...f,
                        selector_config: { ...f.selector_config, [key]: e.target.value },
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            <Check className="h-4 w-4 mr-1" />
            {t('admin.save')}
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
            {t('admin.cancel')}
          </Button>
        </div>
      </div>
    )
  }

  // ── View mode ───────────────────────────────────────────────────────────────
  return (
    <>
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex flex-col gap-3">
          {/* Top row: name + badge/actions */}
          <div className="flex items-start justify-between gap-3">
            <p className="font-bold text-lg leading-snug">{setting.name}</p>
            <div className="flex items-center gap-1 shrink-0">
              <ActiveBadge
                active={setting.is_active}
                onToggle={() => onUpdate(setting.id, { is_active: !setting.is_active })}
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setEditing(true)}
              >
                <Pencil className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive"
                onClick={() => setConfirmDelete(true)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Middle row: countdown + frequency (right-aligned) */}
          <div className="flex justify-end">
            <div className="text-right leading-tight space-y-0.5">
              {setting.is_active && (
                <p className="text-xs font-medium text-orange-500 tabular-nums">
                  {t('admin.nextScrapeIn')} {countdown}
                </p>
              )}
              <p className="text-xs text-muted-foreground">{formatFrequency(setting.frequency)}</p>
            </div>
          </div>

          {/* Bottom row: URL (left) + activity graph (right) */}
          <div className="flex items-end justify-between gap-3">
            {setting.url ? (
              <a
                href={setting.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-primary hover:underline truncate max-w-xs"
              >
                {setting.url}
              </a>
            ) : (
              <span />
            )}
            <ActivityGraph activity={setting.activity} />
          </div>
        </div>

        {isRss && rssKeywords && onAddRssKeyword && onDeleteRssKeyword && (
          <div className="border-t border-border pt-4">
            <RssKeywordManager
              keywords={rssKeywords}
              onAdd={onAddRssKeyword}
              onDelete={onDeleteRssKeyword}
            />
          </div>
        )}
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{t('admin.deleteSource')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t('admin.confirmDeleteSource').replace('{name}', setting.name)}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              {t('admin.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmDelete(false)
                onDelete(setting.id)
              }}
            >
              {t('admin.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
