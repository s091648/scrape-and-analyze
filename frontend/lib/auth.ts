import NextAuth, { type NextAuthOptions } from 'next-auth'
import type { Account, Profile, Session, User } from 'next-auth'
import type { JWT } from 'next-auth/jwt'
import CredentialsProvider from 'next-auth/providers/credentials'
import GoogleProvider from 'next-auth/providers/google'
import { BACKEND_URL as BACKEND_URL_ENV, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, NODE_ENV } from '@/lib/env.server'

// auth.ts runs server-side only (NextAuth callbacks). Use BACKEND_URL (not NEXT_PUBLIC_*)
// so it reads Docker's internal hostname (http://backend:8000) at runtime.
const BACKEND_URL = BACKEND_URL_ENV || 'http://localhost:8000'
// Refresh a bit before actual expiry so a request never races an about-to-expire
// token — mirrors AuthTokenProvider's guest-token refresh margin.
const REFRESH_MARGIN_MS = 60_000

/** Exchanges the refresh token for a new access token via POST /auth/refresh.
 * On failure, returns the token unchanged (still carrying the now-stale
 * accessToken) — apiFetch()'s existing 401 handler already forces a sign-out
 * the next time it's used, so no separate "refresh failed" plumbing is needed. */
async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: token.refreshToken }),
    })
    if (!res.ok) return token
    const data = await res.json()
    return {
      ...token,
      accessToken: data.access_token,
      accessTokenExpires: Date.now() + data.expires_in * 1000,
    }
  } catch {
    return token
  }
}

export const authConfig: NextAuthOptions = {
  debug: NODE_ENV === 'development',
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.username || !credentials?.password) return null
        try {
          const res = await fetch(`${BACKEND_URL}/auth/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: credentials.username,
              password: credentials.password,
            }),
          })
          if (!res.ok) return null
          const user = await res.json()
          return {
            id: user.id,
            name: user.name ?? user.username,
            email: user.email,
            role: user.role,
            accessToken: user.access_token,
            refreshToken: user.refresh_token,
            expiresIn: user.expires_in,
          }
        } catch {
          return null
        }
      },
    }),

    // Login provider: user must already exist in DB
    GoogleProvider({
      id: 'google-login',
      clientId: GOOGLE_CLIENT_ID!,
      clientSecret: GOOGLE_CLIENT_SECRET!,
    }),

    // Register provider: creates a new user in DB
    GoogleProvider({
      id: 'google-register',
      clientId: GOOGLE_CLIENT_ID!,
      clientSecret: GOOGLE_CLIENT_SECRET!,
    }),
  ],

  session: { strategy: 'jwt' },

  callbacks: {
    async signIn({ user, account }: { user: User; account: Account | null; profile?: Profile }) {
      if (account?.provider === 'google-login') {
        try {
          const res = await fetch(`${BACKEND_URL}/auth/google/authorize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: user.email,
              google_id: account.providerAccountId,
              name: user.name,
            }),
          })
          if (res.status === 404) return '/login?error=not_registered'
          if (res.status === 403) return '/login?error=account_disabled'
          if (res.status === 409) return '/login?error=link_required'
          if (!res.ok) return false
          const dbUser = await res.json()
          user.id = dbUser.id
          ;(user as any).role = dbUser.role
          ;(user as any).accessToken = dbUser.access_token
          ;(user as any).refreshToken = dbUser.refresh_token
          ;(user as any).expiresIn = dbUser.expires_in
          return true
        } catch {
          return false
        }
      }

      if (account?.provider === 'google-register') {
        try {
          const res = await fetch(`${BACKEND_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: user.email,
              name: user.name,
              google_id: account.providerAccountId,
            }),
          })
          if (res.status === 409) return '/register?error=already_registered'
          if (!res.ok) return false
          const dbUser = await res.json()
          user.id = dbUser.id
          ;(user as any).role = dbUser.role
          ;(user as any).accessToken = dbUser.access_token
          ;(user as any).refreshToken = dbUser.refresh_token
          ;(user as any).expiresIn = dbUser.expires_in
          return true
        } catch {
          return false
        }
      }

      // credentials: authorize() already validated
      return true
    },

    async jwt({ token, user }: { token: JWT; user?: User }) {
      if (user) {
        token.userId = user.id
        token.role = (user as any).role
        // Backend is the sole issuer of these tokens (auth_service.create_user_access_token /
        // create_user_refresh_token) — NextAuth only relays and refreshes them, it never signs
        // its own.
        token.accessToken = (user as any).accessToken
        token.refreshToken = (user as any).refreshToken
        token.accessTokenExpires = Date.now() + ((user as any).expiresIn as number) * 1000
        return token
      }

      if (Date.now() < (token.accessTokenExpires as number) - REFRESH_MARGIN_MS) {
        return token
      }

      return refreshAccessToken(token)
    },

    async session({ session, token }: { session: Session; token: JWT }) {
      if (session.user) {
        (session.user as any).role = token.role
        ;(session.user as any).id = token.userId
      }
      ;(session as any).accessToken = token.accessToken as string
      return session
    },
  },

  pages: { signIn: '/login' },
}

export default NextAuth(authConfig)
