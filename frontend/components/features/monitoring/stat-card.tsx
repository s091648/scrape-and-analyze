'use client'

import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

interface StatCardProps {
  title: string
  value?: string | number | null
  unit?: string
  loading?: boolean
  error?: boolean
  className?: string
}

export function StatCard({ title, value, unit, loading, error, className }: StatCardProps) {
  return (
    <div className={cn('rounded-lg border border-border bg-card p-4 flex flex-col gap-1', className)}>
      <p className="text-xs font-medium text-muted-foreground truncate">{title}</p>
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
