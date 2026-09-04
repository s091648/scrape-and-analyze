/**
 * Client-safe environment access — the only env vars readable from a
 * "use client" component (025-iac-provisioning US5, FR-018). Two kinds of
 * values are safe to export here, and both are handled the same way at build
 * time (Next.js inlines the literal value into the client bundle):
 *   1. `NEXT_PUBLIC_*` vars — Next.js's own automatic convention.
 *   2. `APP_ENV` / `SENTRY_DSN` — NOT `NEXT_PUBLIC_`-prefixed, but explicitly
 *      whitelisted for client exposure via next.config.ts's `env` block
 *      (deliberate: neither is a secret, and duplicating them under a
 *      NEXT_PUBLIC_ name would be pure noise — see next.config.ts's comment).
 *
 * Never add a var here without also checking whether it actually IS one of
 * the two categories above — anything else silently evaluates to `undefined`
 * in the browser, which is easy to miss (see env.server.ts for the rest).
 */

// Raw values (string | undefined) — each call site applies its own historical
// fallback rather than this module baking in one default that might not
// match every caller.
export const APP_ENV = process.env.APP_ENV
export const SENTRY_DSN = process.env.SENTRY_DSN
export const NEXT_PUBLIC_CHAT_ENDPOINT = process.env.NEXT_PUBLIC_CHAT_ENDPOINT
