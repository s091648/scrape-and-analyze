import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path } = await params
    const searchParams = request.nextUrl.searchParams.toString()
    const targetPath = path.join('/')
    const url = searchParams
      ? `${BACKEND_URL}/${targetPath}?${searchParams}`
      : `${BACKEND_URL}/${targetPath}`

    console.log('[proxy]', request.method, url)

    const headers = new Headers(request.headers)
    headers.delete('host')

    const hasBody = request.method !== 'GET' && request.method !== 'HEAD'

    const response = await fetch(url, {
      method: request.method,
      headers,
      ...(hasBody && { body: await request.text() }),
    })

    const responseHeaders = new Headers(response.headers)
    responseHeaders.delete('transfer-encoding')

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    })
  } catch (err) {
    console.error('[proxy] error:', err)
    return NextResponse.json({ error: String(err) }, { status: 502 })
  }
}

export const GET = handler
export const POST = handler
export const PUT = handler
export const PATCH = handler
export const DELETE = handler
