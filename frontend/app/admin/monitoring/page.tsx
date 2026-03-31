import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authConfig } from '@/lib/auth'
import { MonitoringContent } from './monitoring-content'

export default async function MonitoringPage() {
  const session = await getServerSession(authConfig)

  if (!session) redirect('/login')
  if ((session.user as any)?.role !== 'admin') redirect('/settings')

  // Read server-side only — same variable name used by src/ scraper service,
  // no NEXT_PUBLIC_ prefix needed since this runs only on the server.
  const grafanaUrl = process.env.GRAFANA_URL ?? ''
  const grafanaSaToken = process.env.GRAFANA_SA_TOKEN ?? ''

  return <MonitoringContent grafanaUrl={grafanaUrl} grafanaSaToken={grafanaSaToken} />
}
