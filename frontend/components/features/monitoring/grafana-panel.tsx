'use client'

import { cn } from '@/lib/utils'

interface GrafanaPanelProps {
  grafanaUrl: string
  dashboardUid: string
  panelId: number
  title?: string
  height?: number
  from?: string
  to?: string
  className?: string
  refreshInterval?: number
}

/**
 * Legacy placeholder — Grafana Cloud free tier does not support iframe or image renderer.
 * Use MetricsChart, LogsTable, or TracesTable for live data.
 */
export function GrafanaPanel({
  grafanaUrl,
  title,
  panelId,
  height = 200,
  className,
}: GrafanaPanelProps) {
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <div className="w-full h-full flex flex-col items-center justify-center border border-dashed border-muted-foreground/40 rounded-lg text-muted-foreground">
        <span className="text-sm">Grafana not configured</span>
        <span className="text-xs mt-1">{title ?? `Panel ${panelId}`}</span>
        {grafanaUrl && (
          <span className="text-xs mt-0.5 opacity-60">Use MetricsChart / LogsTable / TracesTable instead</span>
        )}
      </div>
    </div>
  )
}
