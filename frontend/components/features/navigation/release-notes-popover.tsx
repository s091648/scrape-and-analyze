'use client'
import { useEffect, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

interface ReleaseChange {
  type: 'feat' | 'fix' | 'chore'
  description: string
}

interface ReleaseEntry {
  version: string
  date: string
  changes: ReleaseChange[]
}

const STORAGE_KEY = 'last_seen_release_version'

const TYPE_STYLES: Record<string, string> = {
  feat: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  fix: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  chore: 'bg-muted text-muted-foreground',
}

function isPending(version: string) {
  return version.includes('{{')
}

function latestRealVersion(entries: ReleaseEntry[]): string | null {
  return entries.find(e => !isPending(e.version))?.version ?? null
}

// Shimmer beam animation injected once per page load
const SHIMMER_CSS = `
@property --rn-beam-angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}
@keyframes rn-beam-spin {
  to { --rn-beam-angle: 360deg; }
}
.rn-latest-beam {
  background: conic-gradient(
    from var(--rn-beam-angle),
    transparent 0%,
    transparent 33%,
    #b45309 43%,
    #fbbf24 48%,
    #fef9c3 50%,
    #fbbf24 52%,
    #b45309 57%,
    transparent 67%,
    transparent 100%
  );
  animation: rn-beam-spin 2.8s linear infinite;
}
`

let styleInjected = false
function injectStyle() {
  if (styleInjected || typeof document === 'undefined') return
  const el = document.createElement('style')
  el.textContent = SHIMMER_CSS
  document.head.appendChild(el)
  styleInjected = true
}

export function ReleaseNotesPopover() {
  const [entries, setEntries] = useState<ReleaseEntry[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastSeen, setLastSeen] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  // Eagerly fetch on mount so the unread dot shows without opening the popover first
  useEffect(() => {
    setLastSeen(localStorage.getItem(STORAGE_KEY))
    injectStyle()
    setLoading(true)
    fetch('/release-notes.json')
      .then(r => r.json())
      .then((data: ReleaseEntry[]) => setEntries(data))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [])

  function handleOpenChange(next: boolean) {
    setOpen(next)
    if (next && entries) {
      // Mark latest real version as seen when popover is opened
      const latest = latestRealVersion(entries)
      if (latest) {
        localStorage.setItem(STORAGE_KEY, latest)
        setLastSeen(latest)
      }
    }
  }

  const visibleEntries = entries?.filter(e => !isPending(e.version) || e.changes.length > 0) ?? []
  const latestVersion = entries ? latestRealVersion(entries) : null
  const hasUnread = latestVersion !== null && lastSeen !== latestVersion

  return (
    <TooltipProvider>
      <Tooltip>
        <Popover open={open} onOpenChange={handleOpenChange}>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="relative text-muted-foreground hover:text-foreground transition-colors duration-200 cursor-pointer"
                aria-label="Release notes"
              >
                <ScrollText className="h-5 w-5" />
                {hasUnread && (
                  <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-500 ring-1 ring-background" />
                )}
              </button>
            </PopoverTrigger>
          </TooltipTrigger>

          <PopoverContent align="end" className="w-96 p-0 max-h-[480px] flex flex-col">
            <div className="px-4 py-3 border-b border-border shrink-0">
              <p className="font-semibold text-sm">Release Notes</p>
            </div>
            <div className="overflow-y-auto flex-1">
              {loading && (
                <div className="px-4 py-6 text-sm text-muted-foreground text-center">Loading…</div>
              )}
              {!loading && visibleEntries.length === 0 && (
                <div className="px-4 py-6 text-sm text-muted-foreground text-center">No releases yet.</div>
              )}
              {!loading && visibleEntries.map((entry, i) => {
                const isLatest = i === 0
                const isUpcoming = isPending(entry.version)

                const inner = (
                  <div className="px-4 py-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs font-mono font-semibold px-1.5 py-0.5 rounded ${
                        isUpcoming
                          ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
                          : isLatest
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 ring-1 ring-amber-400/60'
                            : 'bg-muted text-muted-foreground'
                      }`}>
                        {isUpcoming ? 'upcoming' : entry.version}
                      </span>
                      {!isUpcoming && (
                        <span className="text-xs text-muted-foreground">{entry.date}</span>
                      )}
                      {isLatest && !isUpcoming && (
                        <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">latest</span>
                      )}
                    </div>
                    {entry.changes.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic">Changes will be filled in before release.</p>
                    ) : (
                      <ul className="space-y-1.5">
                        {entry.changes.map((c, j) => (
                          <li key={j} className="flex items-start gap-2 text-xs">
                            <span className={`shrink-0 mt-0.5 px-1 py-px rounded font-mono text-[10px] font-medium ${TYPE_STYLES[c.type] ?? TYPE_STYLES.chore}`}>
                              {c.type}
                            </span>
                            <span className="text-foreground/80">{c.description}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )

                return (
                  <div key={entry.version}>
                    {isLatest && !isUpcoming ? (
                      // Gold shimmer border wrapper for latest real version
                      <div className="p-[1.5px] rn-latest-beam">
                        <div className="bg-popover rounded-[calc(0.375rem-1px)]">
                          {inner}
                        </div>
                      </div>
                    ) : (
                      inner
                    )}
                    {i < visibleEntries.length - 1 && (
                      <hr className="border-border" />
                    )}
                  </div>
                )
              })}
            </div>
          </PopoverContent>
        </Popover>

        <TooltipContent side="bottom">Release Notes</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
