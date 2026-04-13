import * as fs from 'fs'
import * as path from 'path'
import { EncryptJWT } from 'jose'
import { hkdf } from '@panva/hkdf'

// Falls back to a fixed test secret when NEXTAUTH_SECRET is not in the environment.
// Must match the value used in playwright.config.ts webServer env.
export const E2E_SECRET =
  process.env.NEXTAUTH_SECRET || 'e2e-nextauth-secret-local-testing-only'

async function deriveEncryptionKey(secret: string): Promise<Uint8Array> {
  // Matches next-auth v4's getDerivedEncryptionKey(secret, salt="")
  return hkdf('sha256', secret, '', 'NextAuth.js Generated Encryption Key', 32)
}

export default async function globalSetup() {
  const encKey = await deriveEncryptionKey(E2E_SECRET)

  const now = Math.floor(Date.now() / 1000)
  const oneYear = 365 * 24 * 60 * 60

  // EncryptJWT matches next-auth v4's encode() exactly:
  //   new EncryptJWT(token).setProtectedHeader({ alg:"dir", enc:"A256GCM" })
  //     .setIssuedAt().setExpirationTime(...).setJti(...).encrypt(key)
  const token = await new EncryptJWT({
    name: 'Admin',
    email: 'admin@example.com',
    sub: 'admin-test-user',
    role: 'admin',
    userId: 'admin-test-user',
  })
    .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
    .setIssuedAt(now)
    .setExpirationTime(now + oneYear)
    .setJti(crypto.randomUUID())
    .encrypt(encKey)

  const authState = {
    cookies: [
      {
        name: 'next-auth.session-token',
        value: token,
        domain: 'localhost',
        path: '/',
        expires: now + oneYear,
        httpOnly: true,
        secure: false,
        sameSite: 'Lax' as const,
      },
    ],
    origins: [] as string[],
  }

  const outPath = path.join(__dirname, 'fixtures', 'auth-state.json')
  fs.writeFileSync(outPath, JSON.stringify(authState, null, 2))
  console.log(`[global-setup] auth-state.json generated (secret: ${E2E_SECRET.slice(0, 8)}...)`)
}
