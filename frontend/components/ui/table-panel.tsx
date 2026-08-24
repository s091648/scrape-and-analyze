'use client'

import { useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { HelpCircle, RotateCw, Maximize2 } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'

export interface ColumnDef {
  key: string
  label: string
  className?: string
  align?: 'left' | 'right'
}

interface TablePanelProps {
  title: string
  tooltip?: string
  onRefresh?: () => Promise<void>
  columns: ColumnDef[]
  height?: number
  className?: string
  loading?: boolean
  placeholder?: string
  placeholderError?: boolean
  toolbar?: ReactNode
  children?: ReactNode
}

function TableBody({
  columns, height, loading, placeholder, placeholderError, children,
}: Pick<TablePanelProps, 'columns' | 'loading' | 'placeholder' | 'placeholderError' | 'children'> & { height?: number | string }) {
  return (
    <div className="themed-scrollbar rounded-lg border border-border overflow-auto flex-1 min-h-0" style={{ height }}>
      {loading ? (
        <div className="p-3 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}
        </div>
      ) : placeholder ? (
        <div className={cn(
          'w-full h-full flex items-center justify-center text-sm',
          placeholderError ? 'text-destructive' : 'text-muted-foreground'
        )}>
          {placeholder}
        </div>
      ) : (
        <table className="w-full text-xs">
          <thead className="border-b border-border bg-background sticky top-0 z-10">
            <tr>
              {(columns ?? []).map(col => (
                <th
                  key={col.key}
                  className={cn(
                    'px-2 py-1.5 font-medium text-muted-foreground',
                    col.align === 'right' ? 'text-right' : 'text-left',
                    col.className
                  )}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      )}
    </div>
  )
}

export function TablePanel({
  title,
  tooltip,
  onRefresh,
  columns,
  height = 300,
  className,
  loading,
  placeholder,
  placeholderError,
  toolbar,
  children,
}: TablePanelProps) {
  const [refreshing, setRefreshing] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try { await onRefresh?.() } finally { setRefreshing(false) }
  }

  const showData = !loading && !placeholder

  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
          {title}
          {tooltip && (
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="h-3 w-3 shrink-0 cursor-help" data-testid="help-icon" />
              </TooltipTrigger>
              <TooltipContent>{tooltip}</TooltipContent>
            </Tooltip>
          )}
        </p>
        <div className="flex items-center gap-2">
          {showData && toolbar}
          {showData && (
            <button
              onClick={() => setFullscreen(true)}
              className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              aria-label="Fullscreen"
            >
              <Maximize2 className="h-3 w-3" />
            </button>
          )}
          {onRefresh && (
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 cursor-pointer"
              aria-label="Refresh"
            >
              <RotateCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
            </button>
          )}
        </div>
      </div>
      <TableBody columns={columns} height={height} loading={loading} placeholder={placeholder} placeholderError={placeholderError}>
        {children}
      </TableBody>

      {/* Same title/columns/rows, just a near-fullscreen height — for the large log/trace
          tables where 300-400px makes scanning many rows tedious. */}
      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="max-w-[95vw] sm:max-w-[95vw] w-[95vw] max-h-[90vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle className="text-sm">{title}</DialogTitle>
          </DialogHeader>
          {/* flex flex-col here (not just flex-1 min-h-0) so TableBody's own flex-1 below
              actually has a flex container to grow inside — a plain block div can't pass
              flex sizing on to its child, and TableBody's `style={{ height: '100%' }}` alone
              doesn't reliably resolve here either: percentage heights need the containing
              block's height to come from an explicit CSS `height`, not just a flex-grow
              layout result, so it was silently falling back to auto (content-sized) and
              overflowing past max-h-[90vh] with nothing left to scroll. */}
          <div className="flex-1 min-h-0 flex flex-col">
            <TableBody columns={columns} height="100%" loading={loading} placeholder={placeholder} placeholderError={placeholderError}>
              {children}
            </TableBody>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
