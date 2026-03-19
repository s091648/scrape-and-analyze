import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authConfig } from '@/lib/auth'
import { pushToLoki } from '@/lib/loki-logger'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

const REDACT_KEYS = new Set([
  'password', 'hashed_password', 'token', 'access_token', 'refresh_token',
  'secret', 'api_key', 'authorization', 'private_key', 'credentials',
])

function redact(value: unknown): unknown {
  if (typeof value !== 'object' || value === null) return value
  if (Array.isArray(value)) return value.map(redact)
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([k, v]) => [
      k,
      REDACT_KEYS.has(k.toLowerCase()) ? '[REDACTED]' : redact(v),
    ])
  )
}

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const start = Date.now()

  try {
    const { path } = await params
    const searchParams = request.nextUrl.searchParams.toString()
    const targetPath = path.join('/')
    const url = searchParams
      ? `${BACKEND_URL}/${targetPath}?${searchParams}`
      : `${BACKEND_URL}/${targetPath}`

    const headers = new Headers(request.headers)
    headers.delete('host')

    const hasBody = request.method !== 'GET' && request.method !== 'HEAD'
    const bodyText = hasBody ? await request.text() : null

    const response = await fetch(url, {
      method: request.method,
      headers,
      ...(hasBody && bodyText !== null ? { body: bodyText } : {}),
    })

    const responseHeaders = new Headers(response.headers)
    responseHeaders.delete('transfer-encoding')

    // Resolve user session (server-side, no extra round-trip)
    const session = await getServerSession(authConfig)
    const user = session?.user as { id?: string; email?: string; role?: string } | undefined

    // Parse body for logging (best-effort)
    let parsedBody: unknown = null
    if (bodyText) {
      try { parsedBody = JSON.parse(bodyText) } catch { parsedBody = bodyText }
    }

    pushToLoki({
      level: response.status >= 400 ? 'error' : 'info',
      fields: {
        event: 'proxy_request',
        method: request.method,
        path: `/${targetPath}`,
        status_code: response.status,
        duration_ms: Date.now() - start,
        ...(user?.id ? { user_id: user.id } : {}),
        ...(user?.email ? { user_email: user.email } : {}),
        ...(user?.role ? { user_role: user.role } : {}),
        ip: request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ?? null,
        user_agent: request.headers.get('user-agent') ?? null,
        ...(parsedBody !== null ? { request_body: redact(parsedBody) } : {}),
      },
    })

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    })
  } catch (err) {
    console.error('[proxy] error:', err)
    pushToLoki({
      level: 'error',
      fields: {
        event: 'proxy_error',
        path: request.nextUrl.pathname,
        error: String(err),
        duration_ms: Date.now() - start,
      },
    })
    return NextResponse.json({ error: String(err) }, { status: 502 })
  }
}

export const GET = handler
export const POST = handler
export const PUT = handler
export const PATCH = handler
export const DELETE = handler
