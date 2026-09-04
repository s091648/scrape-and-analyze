/**
 * Server-only environment access — Server Components, Route Handlers, and other
 * server-side modules only. Every non-`NEXT_PUBLIC_` env var this app reads at
 * runtime is centralized here (025-iac-provisioning US5, FR-018) — importing
 * `process.env.X` directly anywhere else in `frontend/` app code is no longer
 * allowed (see env.client.ts for the client-safe counterpart).
 *
 * Do NOT import this file from a "use client" component or module — bundling
 * server-only secrets into the client JS bundle is exactly what this split
 * exists to prevent.
 */

// Raw values (string | undefined) — each call site applies its own historical
// fallback (?? / || with whatever default it already used) rather than this
// module baking in one default that might not match every caller.
export const BACKEND_URL = process.env.BACKEND_URL
export const GRAFANA_URL = process.env.GRAFANA_URL
export const GRAFANA_SA_TOKEN = process.env.GRAFANA_SA_TOKEN
export const GRAFANA_LOKI_URL = process.env.GRAFANA_LOKI_URL
export const GRAFANA_LOKI_USER = process.env.GRAFANA_LOKI_USER
export const GRAFANA_API_KEY = process.env.GRAFANA_API_KEY
export const NEXTAUTH_SECRET = process.env.NEXTAUTH_SECRET
export const NEXTAUTH_URL = process.env.NEXTAUTH_URL
export const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID
export const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET
export const NODE_ENV = process.env.NODE_ENV

// Re-exported here so server code has one place to import every var from —
// the value itself is also client-safe (see env.client.ts) since it's
// whitelisted in next.config.ts's `env` block.
export const APP_ENV = process.env.APP_ENV
