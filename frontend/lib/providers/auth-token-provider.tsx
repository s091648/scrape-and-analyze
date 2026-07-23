'use client'
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { setCurrentToken } from '../auth-token-store'

const GUEST_TOKEN_STORAGE_KEY = 'guest_token_pair'
const GUEST_ISSUE_ENDPOINT = '/api/proxy/auth/guest'
const GUEST_REFRESH_ENDPOINT = '/api/proxy/auth/guest/refresh'
// Refresh a bit before actual expiry so a request never races an about-to-expire token.
const REFRESH_MARGIN_MS = 60_000

interface GuestTokenPair {
  accessToken: string
  refreshToken: string
  expiresAt: number
}

interface AuthTokenContextType {
  token: string | undefined
  isLoading: boolean
}

const AuthTokenContext = createContext<AuthTokenContextType>({ token: undefined, isLoading: true })

function loadStoredPair(): GuestTokenPair | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(GUEST_TOKEN_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as GuestTokenPair) : null
  } catch {
    return null
  }
}

function storePair(pair: GuestTokenPair): void {
  try {
    sessionStorage.setItem(GUEST_TOKEN_STORAGE_KEY, JSON.stringify(pair))
  } catch {}
}

function clearStoredPair(): void {
  try {
    sessionStorage.removeItem(GUEST_TOKEN_STORAGE_KEY)
  } catch {}
}

async function issueGuestTokenPair(): Promise<GuestTokenPair | null> {
  try {
    const res = await fetch(GUEST_ISSUE_ENDPOINT, { method: 'POST' })
    if (!res.ok) return null
    const data = await res.json()
    const pair: GuestTokenPair = {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      expiresAt: Date.now() + data.expires_in * 1000,
    }
    storePair(pair)
    return pair
  } catch {
    return null
  }
}

async function refreshGuestAccessToken(refreshToken: string): Promise<GuestTokenPair | null> {
  try {
    const res = await fetch(GUEST_REFRESH_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return null
    const data = await res.json()
    const pair: GuestTokenPair = {
      accessToken: data.access_token,
      refreshToken,
      expiresAt: Date.now() + data.expires_in * 1000,
    }
    storePair(pair)
    return pair
  } catch {
    return null
  }
}

/**
 * Ensures a legitimate anonymous visitor always has a working guest token —
 * transparently reusing a cached one, refreshing it, or issuing a brand-new
 * pair, in that order of preference (spec 018-public-api-auth, User Story 2).
 */
async function ensureValidGuestPair(): Promise<GuestTokenPair | null> {
  const stored = loadStoredPair()
  const now = Date.now()

  if (stored && stored.expiresAt - REFRESH_MARGIN_MS > now) {
    return stored
  }
  if (stored?.refreshToken) {
    const refreshed = await refreshGuestAccessToken(stored.refreshToken)
    if (refreshed) return refreshed
  }
  return issueGuestTokenPair()
}

export function AuthTokenProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession()
  const [guestPair, setGuestPair] = useState<GuestTokenPair | null>(null)
  const [guestLoading, setGuestLoading] = useState(true)
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const sessionToken = (session as any)?.accessToken as string | undefined

  const refreshGuest = useCallback(async () => {
    const pair = await ensureValidGuestPair()
    setGuestPair(pair)
    setGuestLoading(false)
  }, [])

  useEffect(() => {
    if (status === 'loading') return

    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = null
    }

    if (status === 'authenticated') {
      clearStoredPair()
      setGuestPair(null)
      setGuestLoading(false)
      return
    }

    // status === 'unauthenticated'
    refreshGuest()
  }, [status, refreshGuest])

  // Schedule the next silent refresh whenever the active guest pair changes.
  useEffect(() => {
    if (status !== 'unauthenticated' || !guestPair) return

    const delay = Math.max(guestPair.expiresAt - REFRESH_MARGIN_MS - Date.now(), 0)
    const timer = setTimeout(refreshGuest, delay)
    refreshTimerRef.current = timer
    return () => clearTimeout(timer)
  }, [guestPair, status, refreshGuest])

  const token = status === 'authenticated' ? sessionToken : guestPair?.accessToken
  const isLoading = status === 'loading' || (status === 'unauthenticated' && guestLoading)

  useEffect(() => {
    setCurrentToken(token)
  }, [token])

  return (
    <AuthTokenContext.Provider value={{ token, isLoading }}>
      {children}
    </AuthTokenContext.Provider>
  )
}

export function useAuthToken() {
  return useContext(AuthTokenContext)
}
