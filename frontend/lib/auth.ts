import NextAuth, { type NextAuthOptions } from 'next-auth'
import CredentialsProvider from 'next-auth/providers/credentials'
import GoogleProvider from 'next-auth/providers/google'
import { SignJWT } from 'jose'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
const SECRET = process.env.NEXTAUTH_SECRET!

async function makeAccessToken(payload: Record<string, unknown>): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(payload.exp as number ?? Math.floor(Date.now() / 1000) + 86400 * 30)
    .sign(Buffer.from(SECRET ?? ''))
}

export const authConfig: NextAuthOptions = {
  debug: process.env.NODE_ENV === 'development',
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
          return { id: user.id, name: user.name ?? user.username, email: user.email, role: user.role }
        } catch {
          return null
        }
      },
    }),

    // Login provider: user must already exist in DB
    GoogleProvider({
      id: 'google-login',
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),

    // Register provider: creates a new user in DB
    GoogleProvider({
      id: 'google-register',
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],

  session: { strategy: 'jwt' },

  callbacks: {
    async signIn({ user, account }) {
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
          if (!res.ok) return false
          const dbUser = await res.json()
          user.id = dbUser.id
          ;(user as any).role = dbUser.role
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
          return true
        } catch {
          return false
        }
      }

      // credentials: authorize() already validated
      return true
    },

    async jwt({ token, user }) {
      if (user) {
        token.userId = user.id
        token.role = (user as any).role
      }
      return token
    },

    async session({ session, token }) {
      if (session.user) {
        (session.user as any).role = token.role
        ;(session.user as any).id = token.userId
      }
      // Expose a HS256-signed JWT as accessToken for backend Bearer auth
      ;(session as any).accessToken = await makeAccessToken({
        sub: token.userId as string,
        role: token.role as string,
        exp: token.exp,
      })
      return session
    },
  },

  pages: { signIn: '/login' },
}

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig)
