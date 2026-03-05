import { NextRequest, NextResponse } from 'next/server'
import { SignJWT, jwtVerify } from 'jose'

const SECRET = new TextEncoder().encode(process.env.NEXTAUTH_SECRET!)
const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET!
const NEXTAUTH_URL = process.env.NEXTAUTH_URL!
// Internal URL for server-to-server calls (Docker/Railway)
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl
  const code = searchParams.get('code')
  const state = searchParams.get('state')
  const errorParam = searchParams.get('error')

  if (errorParam || !code || !state) {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 1. Verify state JWT
  let userId: string
  let role: string
  try {
    const { payload } = await jwtVerify(state, SECRET)
    userId = payload.userId as string
    role = payload.role as string
    if (!userId) throw new Error('no userId')
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 2. Exchange code for Google tokens
  const redirectUri = `${NEXTAUTH_URL}/api/link-google/callback`
  let googleId: string
  try {
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri: redirectUri,
        grant_type: 'authorization_code',
      }),
    })
    if (!tokenRes.ok) throw new Error('token exchange failed')
    const tokenData = await tokenRes.json()

    // id_token is a JWT; decode without verification (Google already verified it)
    const [, payloadB64] = tokenData.id_token.split('.')
    const idPayload = JSON.parse(Buffer.from(payloadB64, 'base64url').toString())
    googleId = idPayload.sub
    if (!googleId) throw new Error('no sub in id_token')
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  // 3. Construct a short-lived backend bearer token for this user
  const bearerToken = await new SignJWT({ sub: userId, role })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime('2m')
    .sign(SECRET)

  // 4. Call the backend link endpoint
  try {
    const linkRes = await fetch(`${BACKEND_URL}/auth/me/link-google`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bearerToken}`,
      },
      body: JSON.stringify({ google_id: googleId }),
    })
    if (!linkRes.ok) {
      return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
    }
  } catch {
    return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=error`)
  }

  return NextResponse.redirect(`${NEXTAUTH_URL}/settings?linked=success`)
}
