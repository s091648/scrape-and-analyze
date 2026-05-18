import { Skeleton } from '@/components/ui/skeleton'

export function ArticleCardSkeleton() {
  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden p-6 space-y-4">
      <Skeleton className="h-5 w-4/5" />
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/5" />
      </div>
      <div className="flex gap-2 pt-2 border-t border-border">
        <Skeleton className="h-6 w-20 rounded-full" />
        <Skeleton className="h-6 w-24 rounded-full" />
      </div>
    </div>
  )
}

export function ArticleDetailSkeleton() {
  return (
    <div className="space-y-6 py-2">
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="space-y-4 border-t border-border pt-4">
        {[0, 1, 2].map(i => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {[0, 1, 2, 3].map(i => (
            <Skeleton key={i} className="h-5 w-16 rounded-full" />
          ))}
        </div>
      </div>
    </div>
  )
}
