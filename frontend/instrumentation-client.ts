// Next.js convention: this file's top-level code runs once in the browser on
// every page load, before any other client code — no import needed anywhere.
// Graceful no-op if SENTRY_DSN is unset, matching the rest of this repo's
// observability stack (see backend/observability.py). Shares the backend's
// SENTRY_DSN (exposed to the client bundle via next.config.ts's `env`, same
// pattern as APP_ENV) rather than a separate NEXT_PUBLIC_SENTRY_DSN — one
// Sentry project for both, split by the SDK's automatic `platform` tag.
import * as Sentry from '@sentry/browser'

const dsn = process.env.SENTRY_DSN

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NODE_ENV,
    // Backend already has full OTel tracing (backend/observability.py) — this
    // SDK is for browser exception/error tracking only, not perf tracing.
    tracesSampleRate: 0,
  })
}
