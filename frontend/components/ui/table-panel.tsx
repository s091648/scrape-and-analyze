'use client'

import { useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { HelpCircle, RotateCw } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

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
      <div className="rounded-lg border border-border overflow-auto" style={{ height }}>
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
                {columns.map(col => (
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
    </div>
  )
}
