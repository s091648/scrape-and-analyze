import * as fs from 'fs'
import * as path from 'path'
import * as crypto from 'crypto'
import { CompactEncrypt } from 'jose'

// Falls back to a fixed test secret when NEXTAUTH_SECRET is not in the environment.
// Must match the value used in playwright.config.ts webServer env.
export const E2E_SECRET =
  process.env.NEXTAUTH_SECRET || 'e2e-nextauth-secret-local-testing-only'

async function deriveEncryptionKey(secret: string): Promise<CryptoKey> {
  const baseKey = await globalThis.crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    'HKDF',
    false,
    ['deriveKey'],
  )
  return globalThis.crypto.subtle.deriveKey(
    {
      name: 'HKDF',
      hash: 'SHA-256',
      salt: new Uint8Array(),
      info: new TextEncoder().encode('NextAuth.js Generated Encryption Key'),
    },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

export default async function globalSetup() {
  const encKey = await deriveEncryptionKey(E2E_SECRET)

  const now = Math.floor(Date.now() / 1000)
  const oneYear = 365 * 24 * 60 * 60
  const payload = JSON.stringify({
    name: 'Admin',
    email: 'admin@example.com',
    sub: 'admin-test-user',
    iat: now,
    exp: now + oneYear,
    jti: crypto.randomUUID(),
  })

  const token = await new CompactEncrypt(new TextEncoder().encode(payload))
    .setProtectedHeader({ alg: 'dir', enc: 'A256GCM' })
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
