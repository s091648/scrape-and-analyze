import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { parseLogFields, LogDetailDialog } from '@/components/features/monitoring/log-detail-dialog'
import type { LogEntry } from '@/components/features/monitoring/log-detail-dialog'

vi.mock('@/lib/providers', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children, className }: { children: React.ReactNode; className?: string }) =>
    <div className={className}>{children}</div>,
}))

// ── parseLogFields ─────────────────────────────────────────────────────────

describe('parseLogFields', () => {
  it('parses valid JSON and extracts event, traceId, spanId', () => {
    const raw = JSON.stringify({
      level: 'info',
      event: 'article_analyzed',
      trace_id: 'abc123',
      span_id: 'def456',
      article_id: 'xyz',
    })
    const result = parseLogFields(raw)
    expect(result.event).toBe('article_analyzed')
    expect(result.traceId).toBe('abc123')
    expect(result.spanId).toBe('def456')
    expect(result.fields.article_id).toBe('xyz')
    expect(result.fields.level).toBeUndefined()
    expect(result.fields.event).toBeUndefined()
  })

  it('returns empty fields object for non-JSON raw', () => {
    const result = parseLogFields('plain text log line')
    expect(result.fields).toEqual({})
    expect(result.event).toBeUndefined()
    expect(result.traceId).toBeUndefined()
  })

  it('handles missing optional fields gracefully', () => {
    const raw = JSON.stringify({ level: 'error', message: 'oops' })
    const result = parseLogFields(raw)
    expect(result.event).toBeUndefined()
    expect(result.traceId).toBeUndefined()
    expect(result.spanId).toBeUndefined()
  })

  it('strips level, severity, message, msg from fields', () => {
    const raw = JSON.stringify({ level: 'warn', severity: 'WARN', message: 'msg', msg: 'm', extra: 'kept' })
    const { fields } = parseLogFields(raw)
    expect(fields.level).toBeUndefined()
    expect(fields.severity).toBeUndefined()
    expect(fields.message).toBeUndefined()
    expect(fields.msg).toBeUndefined()
    expect(fields.extra).toBe('kept')
  })

  it('extracts exception as its own field, not part of fields', () => {
    const raw = JSON.stringify({ level: 'error', event: 'rag_ingest_failed', exception: 'Traceback (most recent call last):\n  ...' })
    const { fields, exception } = parseLogFields(raw)
    expect(exception).toBe('Traceback (most recent call last):\n  ...')
    expect(fields.exception).toBeUndefined()
  })
})

// ── LogDetailDialog ────────────────────────────────────────────────────────

const makeEntry = (overrides: Partial<LogEntry> = {}): LogEntry => ({
  ts: '14:30:00',
  tsExact: '2026-06-04T14:30:00.123Z',
  level: 'info',
  message: 'article analyzed',
  raw: JSON.stringify({ level: 'info', event: 'article_analyzed', article_id: 'abc' }),
  ...overrides,
})

describe('LogDetailDialog', () => {
  it('renders nothing when entry is null', () => {
    const { container } = render(<LogDetailDialog entry={null} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders dialog when entry is provided', () => {
    render(<LogDetailDialog entry={makeEntry()} onClose={() => {}} />)
    expect(screen.getByTestId('dialog')).toBeDefined()
  })

  it('displays level and message', () => {
    render(<LogDetailDialog entry={makeEntry({ level: 'error', message: 'fetch failed' })} onClose={() => {}} />)
    // 'ERROR' appears in both DialogTitle and the metadata row — use getAllByText
    expect(screen.getAllByText('ERROR').length).toBeGreaterThan(0)
    expect(screen.getByText('fetch failed')).toBeDefined()
  })

  it('displays exact timestamp', () => {
    render(<LogDetailDialog entry={makeEntry()} onClose={() => {}} />)
    expect(screen.getByText('2026-06-04T14:30:00.123Z')).toBeDefined()
  })

  it('displays extra fields from JSON', () => {
    render(<LogDetailDialog entry={makeEntry()} onClose={() => {}} />)
    expect(screen.getByText('article_id')).toBeDefined()
    expect(screen.getByText('abc')).toBeDefined()
  })

  it('shows trace link when traceId is in raw and onOpenTrace is provided', () => {
    const raw = JSON.stringify({ level: 'info', trace_id: 'trace123abc', event: 'done' })
    const onOpenTrace = vi.fn()
    render(
      <LogDetailDialog
        entry={makeEntry({ raw })}
        onClose={() => {}}
        onOpenTrace={onOpenTrace}
      />
    )
    expect(screen.getByText('admin.viewInTrace')).toBeDefined()
  })

  it('does not show trace link when onOpenTrace is not provided', () => {
    const raw = JSON.stringify({ level: 'info', trace_id: 'trace123abc' })
    render(<LogDetailDialog entry={makeEntry({ raw })} onClose={() => {}} />)
    expect(screen.queryByText('admin.viewInTrace')).toBeNull()
  })

  it('calls onOpenTrace and onClose when trace link is clicked', () => {
    const raw = JSON.stringify({ level: 'info', trace_id: 'trace123abc', span_id: 'span1' })
    const onClose = vi.fn()
    const onOpenTrace = vi.fn()
    render(
      <LogDetailDialog
        entry={makeEntry({ raw })}
        onClose={onClose}
        onOpenTrace={onOpenTrace}
      />
    )
    fireEvent.click(screen.getByText('admin.viewInTrace'))
    expect(onClose).toHaveBeenCalledOnce()
    expect(onOpenTrace).toHaveBeenCalledWith('trace123abc', 'span1')
  })

  it('shows env field when entry.env is set', () => {
    render(<LogDetailDialog entry={makeEntry({ env: 'production' })} onClose={() => {}} />)
    expect(screen.getByText('production')).toBeDefined()
  })

  it('shows raw text fallback when raw is not JSON', () => {
    render(<LogDetailDialog entry={makeEntry({ raw: 'plain text log line' })} onClose={() => {}} />)
    expect(screen.getByText('plain text log line')).toBeDefined()
  })

  it('renders exception in its own labeled section, not in the details grid', () => {
    const raw = JSON.stringify({ level: 'error', event: 'rag_ingest_failed', article_id: 'abc', exception: 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: boom' })
    render(<LogDetailDialog entry={makeEntry({ raw, level: 'error' })} onClose={() => {}} />)
    expect(screen.getByText('admin.logFieldException')).toBeDefined()
    expect(screen.getByText(/ValueError: boom/)).toBeDefined()
    // exception must not also appear as a generic "exception" key/value row
    expect(screen.queryByText('exception')).toBeNull()
  })

  it('does not render an exception section when exception is absent', () => {
    render(<LogDetailDialog entry={makeEntry()} onClose={() => {}} />)
    expect(screen.queryByText('admin.logFieldException')).toBeNull()
  })
})
