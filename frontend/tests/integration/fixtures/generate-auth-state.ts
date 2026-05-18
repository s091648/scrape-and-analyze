#!/usr/bin/env npx tsx
/**
 * Generates e2e/fixtures/auth-state.json for Playwright e2e tests.
 *
 * Run locally (NOT in CI — auth-state.json is committed to the repo):
 *   NEXTAUTH_SECRET=<value> npx tsx tests/integration/fixtures/generate-auth-state.ts
 *
 * The NEXTAUTH_SECRET must match the value in .env AND in the GitHub Actions
 * NEXTAUTH_SECRET secret (so CI can use the same committed auth-state.json).
 *
 * Regenerate if tests start failing with auth errors (cookie expiry).
 */
import * as fs from 'fs'
import * as path from 'path'
import * as crypto from 'crypto'
import { CompactEncrypt } from 'jose'

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

async function main() {
  const secret = process.env.NEXTAUTH_SECRET
  if (!secret) {
    throw new Error('NEXTAUTH_SECRET env var is required.\nUsage: NEXTAUTH_SECRET=<value> npx tsx tests/integration/fixtures/generate-auth-state.ts')
  }

  const encKey = await deriveEncryptionKey(secret)

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

  const outPath = path.join(__dirname, 'auth-state.json')
  fs.writeFileSync(outPath, JSON.stringify(authState, null, 2))
  console.log(`Written: ${outPath}`)
  console.log(`Cookie expires: ${new Date((now + oneYear) * 1000).toISOString()}`)
}

main().catch(err => {
  console.error(err.message)
  process.exit(1)
})
