'use client'
import { SessionProvider } from 'next-auth/react'
import { ReactNode } from 'react'

// Access tokens are short-lived (USER_ACCESS_TOKEN_TTL_SECONDS = 1h,
// backend/services/auth_service.py). Without refetchInterval, NextAuth's
// jwt() callback (lib/auth.ts, which does the actual refresh via
// POST /auth/refresh) only reruns when something explicitly re-requests the
// session — e.g. apiFetch()'s 401 handler — so a tab left open across the 1h
// mark would otherwise go stale until its next API call or page reload.
// Polling every 5 minutes keeps it refreshed well ahead of expiry while a tab
// is open, independent of that reactive 401 path.
const REFETCH_INTERVAL_SECONDS = 5 * 60

export default function SessionProviderWrapper({ children }: { children: ReactNode }) {
  return (
    <SessionProvider refetchOnWindowFocus={false} refetchInterval={REFETCH_INTERVAL_SECONDS}>
      {children}
    </SessionProvider>
  )
}