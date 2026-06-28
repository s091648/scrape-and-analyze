import { Skeleton } from '@/components/ui/skeleton'

export function WeeklyReportSkeleton() {
  return (
    <div className="rounded-2xl border border-border overflow-hidden">
      <Skeleton className="w-full h-48" />
      <div className="p-4 space-y-2">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </div>
    </div>
  )
}
