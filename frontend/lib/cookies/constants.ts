// Isomorphic — no 'use client'/'use server' directive. Safe to import from both
// client-side provider code (lib/providers/*) and server-only code (lib/server/ssr-fetch.ts).

export const TOPIC_COOKIE_NAME = 'selectedTopicId'
export const LOCALE_COOKIE_NAME = 'locale'

// 1 year — a long-lived preference, not a session value (specs/021-ssr-public-pages/data-model.md).
export const PREFERENCE_COOKIE_MAX_AGE_SECONDS = 31536000
