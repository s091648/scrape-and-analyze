'use client'

import { Fragment } from 'react'
import { cn } from '@/lib/utils'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ArrowUpRight } from 'lucide-react'
import { useI18n } from '@/lib/providers'

export interface LogEntry {
  ts: string
  tsExact: string
  level: string
  env?: string
  message: string
  details?: string
  raw: string
}

export const LEVEL_COLORS: Record<string, string> = {
  error: 'text-destructive',
  warning: 'text-yellow-500',
  info: 'text-muted-foreground',
}

export const LEVEL_BG: Record<string, string> = {
  error: 'bg-destructive/10 border-destructive/20',
  warning: 'bg-yellow-500/10 border-yellow-500/20',
  info: 'bg-muted/30 border-border',
}

export function parseLogFields(raw: string): {
  fields: Record<string, unknown>
  event?: string
  traceId?: string
  spanId?: string
  exception?: string
} {
  let fields: Record<string, unknown> = {}
  try { fields = JSON.parse(raw) } catch { return { fields } }
  const { level, severity, event, message, msg, trace_id, span_id, exception, ...rest } = fields as Record<string, unknown>
  void level; void severity; void message; void msg
  return {
    fields: rest,
    event: event != null ? String(event) : undefined,
    traceId: trace_id != null ? String(trace_id) : undefined,
    spanId:  span_id  != null ? String(span_id)  : undefined,
    exception: exception != null ? String(exception) : undefined,
  }
}

interface LogDetailDialogProps {
  entry: LogEntry | null
  onClose: () => void
  /** If provided, a "View in trace" link is shown when the log contains a trace_id. */
  onOpenTrace?: (traceId: string, spanId?: string) => void
}

function fieldLabel(k: string, t: (key: string) => string): string {
  const result = t(`admin.logFieldName.${k}`)
  return result.startsWith('admin.logFieldName.') ? k : result
}

export function LogDetailDialog({ entry, onClose, onOpenTrace }: LogDetailDialogProps) {
  const { t } = useI18n()
  if (!entry) return null

  const { fields, event, traceId, spanId, exception } = parseLogFields(entry.raw)
  const extraEntries = Object.entries(fields).filter(([, v]) => v !== null && v !== undefined && v !== '')

  return (
    <Dialog open={!!entry} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className={cn(exception ? 'max-w-2xl' : 'max-w-lg', 'max-h-[85vh] flex flex-col')}>
        <DialogHeader className="shrink-0">
          <DialogTitle className="flex items-center gap-2 text-sm pr-6">
            <span className={cn('font-mono font-bold shrink-0', LEVEL_COLORS[entry.level])}>{entry.level.toUpperCase()}</span>
            <span className="text-muted-foreground font-normal truncate">{entry.message}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3 text-xs overflow-y-auto themed-scrollbar flex-1 min-h-0 pr-1">
          {/* Metadata */}
          <div className={cn('rounded border p-2.5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1', LEVEL_BG[entry.level] ?? 'bg-muted/30 border-border')}>
            <span className="text-muted-foreground">{t('admin.logFieldTime')}</span>
            <span className="font-mono">{entry.tsExact}</span>
            <span className="text-muted-foreground">{t('admin.logFieldLevel')}</span>
            <span className={cn('font-medium', LEVEL_COLORS[entry.level])}>{entry.level.toUpperCase()}</span>
            {entry.env && (
              <>
                <span className="text-muted-foreground">{t('admin.logFieldEnv')}</span>
                <span className="font-mono">{entry.env}</span>
              </>
            )}
            {event && (
              <>
                <span className="text-muted-foreground">{t('admin.logFieldEvent')}</span>
                <span className="font-mono">{event}</span>
              </>
            )}
          </div>

          {/* Trace link */}
          {traceId && onOpenTrace && (
            <button
              onClick={() => { onClose(); onOpenTrace(traceId, spanId) }}
              className="flex items-center gap-1.5 text-primary hover:underline cursor-pointer"
            >
              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
              {t('admin.viewInTrace')}
              <span className="font-mono text-muted-foreground ml-1">{traceId.slice(0, 8)}…</span>
            </button>
          )}

          {extraEntries.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{t('admin.logExtraFields')}</p>
              <div className="rounded border border-border p-2.5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
                {extraEntries.map(([k, v]) => (
                  <Fragment key={k}>
                    <span className="text-muted-foreground shrink-0 whitespace-nowrap">{fieldLabel(k, t)}</span>
                    <span className="font-mono break-all text-foreground/80">{String(v)}</span>
                  </Fragment>
                ))}
              </div>
            </div>
          )}

          {exception && (
            <div className="space-y-1">
              <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">{t('admin.logFieldException')}</p>
              <pre className="rounded border border-border bg-muted/30 p-2.5 font-mono text-[11px] leading-snug whitespace-pre-wrap break-words text-foreground/80">
                {exception}
              </pre>
            </div>
          )}

          {/* Raw line fallback if not JSON */}
          {extraEntries.length === 0 && Object.keys(fields).length === 0 && (
            <div className="rounded border border-border p-2.5 font-mono text-foreground/80 break-all">{entry.raw}</div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
