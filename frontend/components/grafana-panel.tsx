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
}: GrafanaPanelProps) {

  if (!grafanaUrl) {
    return (
      <div
        className={cn('w-full', className)}
        style={{ height }}
      >
        <div
          className="w-full h-full flex flex-col items-center justify-center border border-dashed border-muted-foreground/40 rounded-lg text-muted-foreground"
        >
          <span className="text-sm">Grafana not configured</span>
          <span className="text-xs mt-1">{title ?? `Panel ${panelId}`}</span>
        </div>
      </div>
    )
  }

  const grafanaEmbedUrl = `${grafanaUrl}/d-solo/${dashboardUid}?orgId=1&panelId=${panelId}&from=${from}&to=${to}&theme=dark&kiosk`
  const src = `/api/grafana-embed?url=${encodeURIComponent(grafanaEmbedUrl)}`

  return (
    <div className={cn('w-full', className)}>
      {title && (
        <p className="text-xs font-medium text-muted-foreground mb-1">{title}</p>
      )}
      <iframe
        src={src}
        width="100%"
        height={height}
        frameBorder="0"
        title={title ?? `Grafana panel ${panelId}`}
        className="rounded-lg"
      />
    </div>
  )
}
