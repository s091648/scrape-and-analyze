'use client'

import { useState } from 'react'
import { HelpCircle, RotateCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface StatCardProps {
  title: string
  value?: string | number | null
  unit?: string
  loading?: boolean
  error?: boolean
  className?: string
  tooltip?: string
  onRefresh?: () => Promise<void>
}

export function StatCard({ title, value, unit, loading, error, className, tooltip, onRefresh }: StatCardProps) {
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await onRefresh?.()
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div className={cn('relative rounded-lg border border-border bg-card p-4 flex flex-col gap-1', className)}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground truncate flex items-center gap-1">
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
        {onRefresh && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="ml-1 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50 cursor-pointer"
            aria-label="Refresh"
          >
            <RotateCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
          </button>
        )}
      </div>
      {loading ? (
        <Skeleton className="h-8 w-24 mt-1" />
      ) : error ? (
        <p className="text-sm text-destructive mt-1">—</p>
      ) : value === null || value === undefined ? (
        <p className="text-sm text-muted-foreground mt-1">—</p>
      ) : (
        <p className="text-2xl font-bold tabular-nums leading-none mt-1">
          {value}
          {unit && <span className="text-sm font-normal text-muted-foreground ml-1">{unit}</span>}
        </p>
      )}
    </div>
  )
}