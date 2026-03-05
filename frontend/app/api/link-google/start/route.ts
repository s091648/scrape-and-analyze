import { NextRequest, NextResponse } from 'next/server'
import { jwtVerify } from 'jose'

const SECRET = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!)
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const NEXTAUTH_URL = process.env.NEXTAUTH_URL!

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization')
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  const accessToken = authHeader.slice(7)

  let userId: string
  let role: string
  try {
    const { payload } = await jwtVerify(accessToken, SECRET)
    userId = payload.sub as string
    role = payload.role as string
    if (!userId) throw new Error('no sub')
  } catch {
    return NextResponse.json({ error: 'Invalid token' }, { status: 401 })
  }

  // Short-lived state JWT: survives the Google OAuth round-trip (~5 min)
  const { SignJWT } = await import('jose')
  const state = await new SignJWT({ userId, role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('5m')
    .sign(SECRET)

  const redirectUri = `${NEXTAUTH_URL}/api/link-google/callback`
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: 'openid email profile',
    state,
  })

  // Return JSON so client can navigate with window.location.href
  // (browser can't set custom headers on navigation, and CORS blocks reading redirect URLs)
  return NextResponse.json({ url: `https://accounts.google.com/o/oauth2/v2/auth?${params}` })
}
