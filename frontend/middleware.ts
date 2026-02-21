import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export default function middleware(request: NextRequest) {
  // Route matching for /admin/* — client-side useSession() guard enforces role check
  return NextResponse.next()
}

export const config = {
  matcher: ['/admin/:path*'],
}
