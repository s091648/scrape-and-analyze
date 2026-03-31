import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth/next'
import { authConfig } from '@/lib/auth'

const GRAFANA_URL = process.env.GRAFANA_URL ?? ''
const GRAFANA_SA_TOKEN = process.env.GRAFANA_SA_TOKEN ?? ''

export async function GET(req: NextRequest) {
  const session = await getServerSession(authConfig)
  if (!session) {
    return new NextResponse('Unauthorized', { status: 401 })
  }

  const target = req.nextUrl.searchParams.get('url')
  if (!target) {
    return new NextResponse('Missing url param', { status: 400 })
  }

  // SSRF guard: only proxy requests to the configured Grafana instance
  if (!GRAFANA_URL || !target.startsWith(GRAFANA_URL)) {
    return new NextResponse('Forbidden', { status: 403 })
  }

  try {
    const upstream = await fetch(target, {
      headers: { Authorization: `Bearer ${GRAFANA_SA_TOKEN}` },
    })

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        'content-type': upstream.headers.get('content-type') ?? 'image/png',
        'cache-control': 'no-store',
      },
    })
  } catch {
    return new NextResponse('Bad gateway', { status: 502 })
  }
}
