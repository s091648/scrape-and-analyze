// frontend/lib/loki-logger.ts
// Fire-and-forget Loki push for Next.js server-side code.
// Called WITHOUT await so it never blocks the response.

interface LogEntry {
  level: string
  labels?: Record<string, string>
  fields: Record<string, unknown>
}

export function pushToLoki(entry: LogEntry): void {
  const url = process.env.GRAFANA_LOKI_URL
  const user = process.env.GRAFANA_LOKI_USER
  const key = process.env.GRAFANA_API_KEY

  if (!url || !user || !key) return

  const stream = {
    app: 'frontend',
    env: process.env.NODE_ENV ?? 'production',
    level: entry.level,
    ...entry.labels,
  }

  const line = JSON.stringify({ ...entry.fields, level: entry.level })
  const ts = (Date.now() * 1_000_000).toString()

  const body = JSON.stringify({
    streams: [{ stream, values: [[ts, line]] }],
  })

  const credentials = Buffer.from(`${user}:${key}`).toString('base64')

  // Intentionally not awaited — fire and forget
  fetch(`${url.replace(/\/$/, '')}/push`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Basic ${credentials}`,
    },
    body,
  }).catch((err: unknown) => {
    console.error('[loki-logger] push failed:', err)
  })
}
