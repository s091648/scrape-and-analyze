'use client'

import { PREFERENCE_COOKIE_MAX_AGE_SECONDS } from './constants'

// Both preference cookies (TOPIC_COOKIE_NAME, LOCALE_COOKIE_NAME) are non-httpOnly, so writing
// them from the client is a direct document.cookie set — no Route Handler/Server Action
// round-trip needed (specs/021-ssr-public-pages/contracts/ssr-preference-cookies.md).
export function setPreferenceCookie(name: string, value: string): void {
  if (typeof document === 'undefined') return
  const secure = typeof location !== 'undefined' && location.protocol === 'https:' ? '; Secure' : ''
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${PREFERENCE_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${secure}`
}
