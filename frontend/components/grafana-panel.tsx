'use client'

import { cn } from '@/lib/utils'
import { useEffect, useState } from 'react'

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

  useEffect(() => {
    setCacheBust(Date.now())
    if (!refreshInterval) return
    const id = setInterval(() => setCacheBust(Date.now()), refreshInterval * 1000)
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
      <img
        src={src}
        alt={title ?? `Grafana panel ${panelId}`}
        width={renderWidth}
        height={renderHeight}
        className="w-full rounded-lg"
        style={{ height }}
      />
    </div>
  )
}
