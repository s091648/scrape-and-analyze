'use client'
import { useState, useEffect } from 'react'
import { Pencil, X, Check } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'

export interface ScraperSetting {
  id: string
  source_type: 'rss' | 'blog' | 'arxiv'
  name: string
  url: string
  frequency: number
  is_active: boolean
  selector_config?: { article_link: string; title: string; content: string } | null
  last_scraped_at?: string | null
  activity?: number[] // 14 values oldest→newest (one per day)
}

export function formatFrequency(hours: number): string {
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  const rem = hours % 24
  return rem > 0 ? `${hours}h (= ${days}d ${rem}h)` : `${hours}h (= ${days}d)`
}

function msUntilNextMidnightUTC(): number {
  const now = new Date()
  const nextMidnight = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate() + 1,
  )
  return Math.max(0, nextMidnight - Date.now())
}

function msUntilNextScrape(lastScrapedAt: string | null | undefined, frequencyHours: number): number {
  if (!lastScrapedAt) return msUntilNextMidnightUTC()

  const nextDueMs = new Date(lastScrapedAt).getTime() + frequencyHours * 3600 * 1000
  if (nextDueMs <= Date.now()) return msUntilNextMidnightUTC()

  // Find the next midnight UTC on or after nextDueMs
  const d = new Date(nextDueMs)
  const nextMidnightAfterDue = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1)
  return Math.max(0, nextMidnightAfterDue - Date.now())
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
      {active ? 'active' : 'inactive'}
    </button>
  )
}

// ── Shared form field styles ──────────────────────────────────────────────────

const inputClass =
  'w-full h-9 px-3 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring'
const labelClass = 'block text-xs font-medium mb-1 text-muted-foreground'

// ── SourceCard ────────────────────────────────────────────────────────────────

export function SourceCard({
  setting,
  onUpdate,
  onDelete,
}: {
  setting: ScraperSetting
  onUpdate: (id: string, data: Partial<ScraperSetting>) => Promise<void>
  onDelete: (id: string) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [form, setForm] = useState({
    name: setting.name,
    url: setting.url,
    frequency: setting.frequency,
    is_active: setting.is_active,
    selector_config: setting.selector_config ?? { article_link: '', title: '', content: '' },
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

  // ── Edit mode ───────────────────────────────────────────────────────────────
  if (editing) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Edit Source</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditing(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-3">
          <div>
            <label className={labelClass}>Name</label>
            <input
              className={inputClass}
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelClass}>URL</label>
            <input
              className={inputClass}
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
              placeholder="https://..."
            />
          </div>
          <div>
            <label className={labelClass}>Frequency (hours)</label>
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
            <span className="text-sm text-muted-foreground">Active</span>
          </div>

          {setting.source_type === 'blog' && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                CSS Selectors
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
            Save
          </Button>
          <Button size="sm" variant="outline" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  // ── View mode ───────────────────────────────────────────────────────────────
  return (
    <>
      <div className="rounded-xl border border-border bg-card p-5">
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
              <p className="text-xs font-medium text-orange-500 tabular-nums">
                next scrape in {countdown}
              </p>
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
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete source?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <strong>{setting.name}</strong>? This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirmDelete(false)
                onDelete(setting.id)
              }}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
