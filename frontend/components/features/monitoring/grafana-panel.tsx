'use client'

import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'

interface GrafanaPanelProps {
  grafanaUrl: string
  dashboardUid: string
  panelId: number
  title?: string
  height?: number
  from?: string
  to?: string
  className?: string
  /** Auto-refresh interval in seconds. 0 = disabled. Default: 60 */
  refreshInterval?: number
}

export function GrafanaPanel({
  grafanaUrl,
  dashboardUid,
  panelId,
  title,
  height = 200,
  from = 'now-24h',
  to = 'now',
  className,
  refreshInterval = 60,
}: GrafanaPanelProps) {
  const [cacheBust, setCacheBust] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    setLoaded(false)
    setCacheBust(Date.now())
    if (!refreshInterval) return
    const id = setInterval(() => {
      setLoaded(false)
      setCacheBust(Date.now())
    }, refreshInterval * 1000)
    return () => clearInterval(id)
  }, [refreshInterval])

  if (!grafanaUrl) {
    return (
      <div className={cn('w-full', className)} style={{ height }}>
        <div className="w-full h-full flex flex-col items-center justify-center border border-dashed border-muted-foreground/40 rounded-lg text-muted-foreground">
          <span className="text-sm">Grafana not configured</span>
          <span className="text-xs mt-1">{title ?? `Panel ${panelId}`}</span>
        </div>
      </div>
    )
  }

  // Use Grafana's image renderer endpoint — returns a PNG, no iframe/CSP issues.
  const renderWidth = 1000
  const renderHeight = height * 2 // 2× for retina
  const renderUrl = `${grafanaUrl.replace(/\/$/, '')}/render/d-solo/${dashboardUid}?orgId=1&panelId=${panelId}&from=${from}&to=${to}&theme=dark&width=${renderWidth}&height=${renderHeight}`
  const src = `/api/grafana-embed?url=${encodeURIComponent(renderUrl)}&_=${cacheBust}`

  return (
    <div className={cn('w-full', className)}>
      {title && (
        <p className="text-xs font-medium text-muted-foreground mb-1">{title}</p>
      )}
      <div className="relative w-full rounded-lg overflow-hidden" style={{ height }}>
        {!loaded && (
          <Skeleton className="absolute inset-0 rounded-lg" />
        )}
        <img
          src={src}
          alt={title ?? `Grafana panel ${panelId}`}
          width={renderWidth}
          height={renderHeight}
          className="w-full rounded-lg"
          style={{ height, opacity: loaded ? 1 : 0 }}
          onLoad={() => setLoaded(true)}
          onError={() => setLoaded(true)}
        />
      </div>
    </div>
  )
}
